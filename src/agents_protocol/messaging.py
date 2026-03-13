"""Message broker and routing for agent communication."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict, Optional, Callable, Any, List, cast

from .protocol import AgentMessage, MessageStatus, MessageType
from .persistence import MessageStore
from .agents import Agent, AgentRegistry

logger = logging.getLogger(__name__)


class MessageBroker:
    """Central message broker for routing messages between agents.

    The broker manages agent connections, routes messages based on
    recipient_id, and provides reliable message delivery with
    optional acknowledgments.
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        store: Optional[MessageStore] = None,
    ):
        """Initialize the message broker.

        Args:
            registry: Optional agent registry to use for discovery
            store: Optional message store for persistence and history tracking
        """
        self._agents: Dict[str, Agent] = {}
        self._agent_inboxes: Dict[str, asyncio.Queue] = {}
        self._registry = registry or AgentRegistry()
        self._store = store
        self._running = False
        self._message_timeout = 30.0  # seconds
        self._pending_messages: Dict[str, asyncio.Future] = {}

    async def register_agent(self, agent: Agent) -> None:
        """Register an agent with the broker.

        Args:
            agent: The agent to register
        """
        agent_id = agent.get_agent_id()
        # Update or replace if already registered
        self._agents[agent_id] = agent
        if agent_id not in self._agent_inboxes:
            self._agent_inboxes[agent_id] = asyncio.Queue()
        if agent_id not in self._registry._agents:
            self._registry.register(agent)
        logger.info(f"Agent {agent_id} registered with broker")

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the broker.

        Args:
            agent_id: ID of the agent to unregister
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._agent_inboxes:
            del self._agent_inboxes[agent_id]
        self._registry.unregister(agent_id)
        logger.info(f"Agent {agent_id} unregistered from broker")

    async def send(self, message: AgentMessage) -> MessageStatus:
        """Send a message to its recipient(s).

        Args:
            message: The message to send

        Returns:
            The final status of the message
        """
        message.status = MessageStatus.SENT

        if self._store:
            await self._store.save_message(message)

        if message.recipient_id is None:
            # Broadcast to all agents except sender
            await self._broadcast(message)
            message.status = MessageStatus.DELIVERED
        else:
            # Direct message
            await self._deliver_to_agent(message.recipient_id, message)
            # DELIVERED is functionally set inside _deliver_to_agent or marked FAILED

        return message.status

    async def _deliver_to_agent(self, agent_id: str, message: AgentMessage) -> bool:
        """Deliver a message to a specific agent's inbox.

        Args:
            agent_id: ID of the recipient agent
            message: The message to deliver

        Returns:
            True if delivered successfully, False otherwise
        """
        if agent_id not in self._agent_inboxes:
            logger.warning(f"Agent {agent_id} not found for message {message.id}")
            message.status = MessageStatus.FAILED
            if self._store:
                await self._store.update_message_status(
                    message.id, MessageStatus.FAILED
                )
                await self._store.add_to_dlq(
                    message, f"Agent {agent_id} not registered."
                )
            return False

        try:
            await self._agent_inboxes[agent_id].put(message)
            logger.debug(f"Message {message.id} delivered to agent {agent_id}")
            message.status = MessageStatus.DELIVERED
            if self._store:
                await self._store.update_message_status(
                    message.id, MessageStatus.DELIVERED
                )
            return True
        except Exception as e:
            logger.error(f"Failed to deliver message {message.id} to {agent_id}: {e}")
            message.status = MessageStatus.FAILED
            if self._store:
                await self._store.update_message_status(
                    message.id, MessageStatus.FAILED
                )
                await self._store.add_to_dlq(message, str(e))
            return False

    async def _broadcast(self, message: AgentMessage) -> None:
        """Broadcast a message to all registered agents except sender.

        Args:
            message: The message to broadcast
        """
        sender_id = message.sender_id
        tasks = []
        for agent_id in self._agents:
            if agent_id != sender_id:
                # Create a copy of the message for each recipient
                msg_copy = AgentMessage(
                    id=message.id,
                    type=message.type,
                    sender_id=message.sender_id,
                    recipient_id=agent_id,
                    priority=message.priority,
                    status=message.status,
                    timestamp=message.timestamp,
                    correlation_id=message.correlation_id,
                    reply_to=message.reply_to,
                    content=message.content.copy(),
                    metadata=message.metadata.copy(),
                )
                tasks.append(self._deliver_to_agent(agent_id, msg_copy))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def request(
        self,
        recipient_id: str,
        content: Dict[str, Any],
        message_type: MessageType = MessageType.REQUEST,
        priority: Any = None,
        timeout: float = 30.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[AgentMessage]:
        """Send a request and wait for a response.

        Args:
            recipient_id: ID of the agent to send the request to
            content: The request content
            message_type: Type of message (default: REQUEST)
            priority: Message priority
            timeout: Time to wait for response in seconds
            metadata: Optional metadata

        Returns:
            The response message, or None if timeout
        """
        from .protocol import AgentMessage, MessagePriority

        if priority is None:
            priority = MessagePriority.NORMAL

        correlation_id = str(uuid.uuid4())

        _ = AgentMessage(
            type=message_type,
            sender_id="",  # Will be set by the sending agent
            recipient_id=recipient_id,
            priority=priority,
            correlation_id=correlation_id,
            content=content,
            metadata=metadata or {},
        )

        # Create a future to wait for the response
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_messages[correlation_id] = future

        try:
            # The actual send will be done by the agent
            # This method is meant to be called by an agent
            # So we need to set the sender_id properly
            raise RuntimeError(
                "Broker.request() should not be called directly. "
                "Use agent.send_request() instead."
            )
        finally:
            # Cleanup if needed
            pass

    def set_response(self, correlation_id: str, response: AgentMessage) -> None:
        """Set a response for a pending request.

        This is called internally when a response message is received.

        Args:
            correlation_id: The correlation ID of the pending request
            response: The response message
        """
        if correlation_id in self._pending_messages:
            future = self._pending_messages.pop(correlation_id)
            if not future.done():
                future.set_result(response)

    async def get_next_message_for_agent(self, agent_id: str) -> Optional[AgentMessage]:
        """Get the next message for a specific agent.

        Args:
            agent_id: ID of the agent

        Returns:
            The next message, or None if no message available
        """
        if agent_id not in self._agent_inboxes:
            return None

        try:
            msg = await asyncio.wait_for(
                self._agent_inboxes[agent_id].get(), timeout=0.1
            )
            return cast(AgentMessage, msg)
        except asyncio.TimeoutError:
            return None

    def get_agent_ids(self) -> list:
        """Get list of all registered agent IDs."""
        return list(self._agents.keys())

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    @property
    def registry(self) -> AgentRegistry:
        """Get the agent registry."""
        return self._registry

    @property
    def store(self) -> Optional[MessageStore]:
        """Get the message store instance if attached."""
        return self._store

    async def get_history(self, agent_id: str, limit: int = 100) -> List[AgentMessage]:
        """Fetch message history for an agent directly through the attached store."""
        if not self._store:
            return []
        return await self._store.get_history(agent_id, limit)

    async def replay_message(self, message_id: str) -> bool:
        """Replay a message that exists in the store (e.g., from the DLQ)."""
        if not self._store:
            logger.error("Cannot replay: No MessageStore attached.")
            return False

        message = await self._store.get_message(message_id)
        if not message:
            logger.error(f"Cannot replay: Message {message_id} not found in store.")
            return False

        # Pre-cleanup the message state prior to re-attempting routing
        message.status = MessageStatus.PENDING
        await self._store.remove_from_dlq(message.id)

        # Manually triggering _deliver_to_agent preserves original IDs/intent
        if message.recipient_id is None:
            await self._broadcast(message)
            message.status = MessageStatus.DELIVERED
        else:
            await self._deliver_to_agent(message.recipient_id, message)

        return message.status == MessageStatus.DELIVERED


class MessageRouter:
    """Advanced message router with filtering and routing rules.

    This can be used to implement more complex routing logic
    beyond simple direct addressing.
    """

    def __init__(self) -> None:
        """Initialize the router."""
        self._routes: Dict[str, list] = {}  # capability -> list of agent_ids
        self._filters: list = []

    def add_route(self, pattern: str, agent_ids: List[str]) -> None:
        """Add a routing rule.

        Args:
            pattern: Route pattern (e.g., "capability:summarization")
            agent_ids: List of agent IDs to route to
        """
        self._routes[pattern] = agent_ids

    def add_filter(self, filter_func: Callable[[AgentMessage], bool]) -> None:
        """Add a message filter.

        Args:
            filter_func: Function that returns True if message should be routed
        """
        self._filters.append(filter_func)

    def route(self, message: AgentMessage, available_agents: List[str]) -> List[str]:
        """Route a message to appropriate agents based on rules.

        Args:
            message: The message to route
            available_agents: List of available agent IDs

        Returns:
            List of agent IDs that should receive the message
        """
        recipients: List[str] = []

        # Check routing rules
        for pattern, agent_ids in self._routes.items():
            if self._match_pattern(pattern, message):
                recipients.extend(
                    agent_id for agent_id in agent_ids if agent_id in available_agents
                )

        # Apply filters
        if self._filters:
            recipients = [
                agent_id
                for agent_id in recipients
                if all(filter_func(message) for filter_func in self._filters)
            ]

        return recipients

    def _match_pattern(self, pattern: str, message: AgentMessage) -> bool:
        """Check if a message matches a routing pattern.

        Args:
            pattern: The pattern to match against
            message: The message to check

        Returns:
            True if the pattern matches
        """
        # Simple pattern matching - can be extended
        if pattern.startswith("capability:"):
            _ = pattern.split(":", 1)[1]
            # This would need access to agent registry to check capabilities
            return True  # Placeholder
        return False
