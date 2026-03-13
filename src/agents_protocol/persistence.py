"""Message persistence layer for agents_protocol."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
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
        # Maps message.id to AgentMessage
        self._messages: Dict[str, AgentMessage] = {}
        # Lists of message IDs partitioned by agent
        self._agent_history: Dict[str, List[str]] = {}
        # Maps correlation_id to lists of message IDs
        self._conversations: Dict[str, List[str]] = {}
        # Dead Letter Queue: Dict[message_id,
        #   Dict{"message": AgentMessage, "reason": str, "time": datetime}]
        self._dlq: Dict[str, Dict] = {}

    async def save_message(self, message: AgentMessage) -> None:
        """Save message to in-memory dictionaries."""
        self._messages[message.id] = message

        # Track history for sender
        if message.sender_id:
            if message.sender_id not in self._agent_history:
                self._agent_history[message.sender_id] = []
            if message.id not in self._agent_history[message.sender_id]:
                self._agent_history[message.sender_id].append(message.id)

        # Track history for recipient (if concrete)
        if message.recipient_id:
            if message.recipient_id not in self._agent_history:
                self._agent_history[message.recipient_id] = []
            if message.id not in self._agent_history[message.recipient_id]:
                self._agent_history[message.recipient_id].append(message.id)

        # Track by correlation_id for conversation tracking
        if message.correlation_id:
            if message.correlation_id not in self._conversations:
                self._conversations[message.correlation_id] = []
            if message.id not in self._conversations[message.correlation_id]:
                self._conversations[message.correlation_id].append(message.id)

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
        ids = self._agent_history[agent_id][-limit:]
        return [self._messages[msg_id] for msg_id in ids if msg_id in self._messages]

    async def get_conversation(self, correlation_id: str) -> List[AgentMessage]:
        """Get the full thread tracking a given correlation ID."""
        if correlation_id not in self._conversations:
            return []

        ids = self._conversations[correlation_id]
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
        items = list(self._dlq.values())
        # Sort by failed_at timestamp (ascending)
        items.sort(key=lambda x: x["failed_at"])
        return items[-limit:]

    async def remove_from_dlq(self, message_id: str) -> None:
        """Remove an item from the DLQ by ID."""
        if message_id in self._dlq:
            del self._dlq[message_id]
