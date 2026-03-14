"""Message persistence layer for agents_protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
import heapq
from .protocol import AgentMessage, MessageStatus


class MessageStore(ABC):
    """Abstract base class for message persistence.

    Implementations of this class handle saving messages, retrieving
    history, and managing dead-letter queues across various storage
    backends (e.g. Memory, SQLite, Redis).
    """

    @abstractmethod
    async def save_message(self, message: AgentMessage) -> None:
        """Save a message to the store."""

    @abstractmethod
    async def update_message_status(
        self, message_id: str, status: MessageStatus
    ) -> None:
        """Update the status of an existing message."""

    @abstractmethod
    async def get_message(self, message_id: str) -> Optional[AgentMessage]:
        """Retrieve a message by its ID."""

    @abstractmethod
    async def get_history(self, agent_id: str, limit: int = 100) -> List[AgentMessage]:
        """Get the message history for a specific agent (sent and received)."""

    @abstractmethod
    async def get_conversation(self, correlation_id: str) -> List[AgentMessage]:
        """Get all messages associated with a correlation ID."""

    @abstractmethod
    async def add_to_dlq(self, message: AgentMessage, reason: str) -> None:
        """Add a failed message to the Dead Letter Queue."""

    @abstractmethod
    async def get_dlq(self, limit: int = 100) -> List[Dict]:
        """Retrieve items from the DLQ. Each list item should contain at least
        'message' (the AgentMessage) and 'reason' (string)."""

    @abstractmethod
    async def remove_from_dlq(self, message_id: str) -> None:
        """Remove a message from the DLQ (e.g., after successful replay)."""


class InMemoryMessageStore(MessageStore):
    """In-memory implementation of the MessageStore interface.

    Useful for local testing, development, and scenarios where
    persistence across application restarts is not required.
    """

    def __init__(self) -> None:
        import collections

        # Maps message.id to AgentMessage
        self._messages: Dict[str, AgentMessage] = {}
        # Lists of message IDs partitioned by agent
        self._agent_history: Dict[str, collections.deque] = {}
        self._agent_history_sets: Dict[str, set] = {}
        # Maps correlation_id to lists of message IDs
        self._conversations: Dict[str, collections.deque] = {}
        self._conversation_sets: Dict[str, set] = {}
        # Dead Letter Queue
        self._dlq: Dict[str, Dict] = {}
        self.MAX_HISTORY = 1000

    def _add_to_history(self, history_dict, set_dict, key, msg_id):
        import collections

        if key not in history_dict:
            history_dict[key] = collections.deque(maxlen=self.MAX_HISTORY)
            set_dict[key] = set()
        if msg_id not in set_dict[key]:
            if len(history_dict[key]) == self.MAX_HISTORY:
                old_id = history_dict[key].popleft()
                set_dict[key].discard(old_id)
            history_dict[key].append(msg_id)
            set_dict[key].add(msg_id)

    async def save_message(self, message: AgentMessage) -> None:
        """Save message to in-memory dictionaries."""
        self._messages[message.id] = message

        # Track history for sender
        if message.sender_id:
            self._add_to_history(
                self._agent_history,
                self._agent_history_sets,
                message.sender_id,
                message.id,
            )

        # Track history for recipient (if concrete)
        if message.recipient_id:
            self._add_to_history(
                self._agent_history,
                self._agent_history_sets,
                message.recipient_id,
                message.id,
            )

        # Track by correlation_id for conversation tracking
        if message.correlation_id:
            self._add_to_history(
                self._conversations,
                self._conversation_sets,
                message.correlation_id,
                message.id,
            )

    async def update_message_status(
        self, message_id: str, status: MessageStatus
    ) -> None:
        """Update message status in memory."""
        if message_id in self._messages:
            self._messages[message_id].status = status

    async def get_message(self, message_id: str) -> Optional[AgentMessage]:
        """Fetch a message by ID."""
        return self._messages.get(message_id)

    async def get_history(self, agent_id: str, limit: int = 100) -> List[AgentMessage]:
        """Retrieve last $limit messages relating to agent_id ordered functionally."""
        if agent_id not in self._agent_history:
            return []

        # Get message IDs, grab objects from store, return tail truncated to limit
        ids = list(self._agent_history[agent_id])[-limit:]
        return [self._messages[msg_id] for msg_id in ids if msg_id in self._messages]

    async def get_conversation(self, correlation_id: str) -> List[AgentMessage]:
        """Get the full thread tracking a given correlation ID."""
        if correlation_id not in self._conversations:
            return []

        ids = list(self._conversations[correlation_id])
        return [self._messages[msg_id] for msg_id in ids if msg_id in self._messages]

    async def add_to_dlq(self, message: AgentMessage, reason: str) -> None:
        """Add message to the Dead Letter Queue."""
        # Ensure we also save the original message state globally if it isn't
        # tracked yet
        await self.save_message(message)

        self._dlq[message.id] = {
            "message": message,
            "reason": reason,
            "failed_at": datetime.now(),
        }

    async def get_dlq(self, limit: int = 100) -> List[Dict]:
        """Get the top $limit items from the DLQ dict, ordered chronologically."""
        items = heapq.nlargest(limit, self._dlq.values(), key=lambda x: x["failed_at"])
        items.sort(key=lambda x: x["failed_at"])
        return items

    async def remove_from_dlq(self, message_id: str) -> None:
        """Remove an item from the DLQ by ID."""
        if message_id in self._dlq:
            del self._dlq[message_id]
