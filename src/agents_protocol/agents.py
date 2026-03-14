"""Agent base classes and registry for managing agents."""

from __future__ import annotations

from typing import Dict, Optional, Any, Callable, TYPE_CHECKING, Awaitable
from .protocol import AgentMessage, AgentProtocol, MessageType, MessageStatus
from .extensions import HookManager, AgentHook
import asyncio
import logging

if TYPE_CHECKING:
    from .messaging import MessageBroker

logger = logging.getLogger(__name__)


class Agent(AgentProtocol):
    """Base class for all AI agents using the agents_protocol.

    This provides a foundation that agents can extend to implement
    their specific behavior while maintaining protocol compliance.

    Attributes:
        agent_id: Unique identifier for this agent
        name: Human-readable name
        capabilities: List of capabilities this agent provides
        metadata: Additional metadata about the agent
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the agent.

        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable name
            capabilities: List of capabilities this agent provides
            metadata: Additional metadata about the agent
        """
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self._message_handlers: Dict[MessageType, Callable] = {}
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._broker: Optional["MessageBroker"] = None
        self._hooks = HookManager()

    def get_agent_id(self) -> str:
        """Get the unique identifier for this agent."""
        return self.agent_id

    def get_info(self) -> Dict[str, Any]:
        """Get agent information for discovery."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }

    def register_handler(self, message_type: MessageType, handler: Callable) -> None:
        """Register a handler for a specific message type.

        Args:
            message_type: The type of message to handle
            handler: Async function that takes an AgentMessage and returns a response
        """
        self._message_handlers[message_type] = handler
        logger.debug(f"Registered handler for {message_type} on agent {self.agent_id}")

    def register_hook(
        self, hook: AgentHook, callback: Callable[..., Awaitable[None]]
    ) -> None:
        """Register a lifecycle hook.

        Args:
            hook: The hook type
            callback: Async function to call
        """
        self._hooks.register(hook, callback)

    async def send_message(self, message: AgentMessage) -> MessageStatus:
        """Send a message to another agent via the broker.

        Args:
            message: The message to send

        Returns:
            The status of the sent message
        """
        if not self._broker:
            raise RuntimeError(f"Agent {self.agent_id} is not connected to a broker")

        message.sender_id = self.agent_id
        status = await self._broker.send(message)
        return status

    async def receive_message(self) -> Optional[AgentMessage]:
        """Receive a message from the agent's inbox.

        Returns:
            The received message, or None if no message available
        """
        try:
            if self._broker:
                # Get from broker's inbox if available
                message = await self._broker.get_next_message_for_agent(self.agent_id)
                if message:
                    return message
            # Fall back to local inbox
            message = await asyncio.wait_for(self._inbox.get(), timeout=1.0)
            return message
        except asyncio.TimeoutError:
            return None

    async def broadcast(self, message: AgentMessage) -> None:
        """Broadcast a message to all agents via the broker.

        Args:
            message: The message to broadcast
        """
        if not self._broker:
            raise RuntimeError(f"Agent {self.agent_id} is not connected to a broker")

        message.sender_id = self.agent_id
        message.recipient_id = None  # Broadcast
        await self._broker.send(message)

    async def _process_message(self, message: AgentMessage) -> None:
        """Process an incoming message using registered handlers.

        Args:
            message: The message to process
        """
        await self._hooks.trigger(AgentHook.PRE_MESSAGE_PROCESS, self, message)
        try:
            handler = self._message_handlers.get(message.type)
            if handler:
                response = await handler(message)
                if response and message.type == MessageType.REQUEST:
                    # Send response if handler returns one
                    response_message = message.create_reply(response)
                    await self.send_message(response_message)
            else:
                logger.warning(
                    f"No handler registered for message type "
                    f"{message.type} from {message.sender_id}"
                )
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            # Send error response if this was a request
            if message.type == MessageType.REQUEST:
                error_response = message.create_reply(
                    {"error": str(e)}, {"error_type": type(e).__name__}
                )
                error_response.type = MessageType.ERROR
                await self.send_message(error_response)
        finally:
            await self._hooks.trigger(AgentHook.POST_MESSAGE_PROCESS, self, message)

    async def _message_loop(self) -> None:
        """Main message processing loop."""
        while self._running:
            try:
                message = await self.receive_message()
                if message:
                    await self._process_message(message)
            except Exception as e:
                logger.error(f"Error in message loop for agent {self.agent_id}: {e}")
                await asyncio.sleep(0.1)

    async def connect(self, broker: "MessageBroker") -> None:
        """Connect the agent to a message broker.

        Args:
            broker: The message broker to use
        """
        await self._hooks.trigger(AgentHook.PRE_CONNECT, self, broker)
        self._broker = broker
        if self.agent_id not in broker._agents:
            await broker.register_agent(self)
        else:
            # Agent already registered, just update broker reference
            broker._agents[self.agent_id] = self
        self._running = True
        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())

        def _handle_exception(task):
            if not task.cancelled() and task.exception():
                logger.error(
                    f"Message loop crashed for agent {self.agent_id}: "
                    f"{task.exception()}"
                )

        self._loop_task.add_done_callback(_handle_exception)

        logger.info(f"Agent {self.agent_id} connected to broker")
        await self._hooks.trigger(AgentHook.POST_CONNECT, self, broker)

    async def disconnect(self) -> None:
        """Disconnect the agent from the broker."""
        await self._hooks.trigger(AgentHook.PRE_DISCONNECT, self)
        self._running = False
        if hasattr(self, "_loop_task") and self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        if self._broker:
            await self._broker.unregister_agent(self.agent_id)
            self._broker = None
        logger.info(f"Agent {self.agent_id} disconnected")
        await self._hooks.trigger(AgentHook.POST_DISCONNECT, self)

    async def is_connected(self) -> bool:
        """Check if the agent is connected."""
        return self._running and self._broker is not None

    def set_broker(self, broker: "MessageBroker") -> None:
        """Set the broker for this agent (for backward compatibility)."""
        self._broker = broker


class AgentRegistry:
    """Registry for discovering and managing agents.

    This provides a central registry where agents can register themselves
    and other agents can discover available agents and their capabilities.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._agents: Dict[str, Agent] = {}
        self._capabilities_index: Dict[str, list] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent in the registry.

        Args:
            agent: The agent to register
        """
        self._agents[agent.agent_id] = agent

        # Index by capabilities
        for capability in agent.capabilities:
            if capability not in self._capabilities_index:
                self._capabilities_index[capability] = []
            self._capabilities_index[capability].append(agent.agent_id)

        logger.info(f"Registered agent {agent.agent_id} ({agent.name})")

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent from the registry.

        Args:
            agent_id: ID of the agent to unregister
        """
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            # Remove from capability index
            for capability in agent.capabilities:
                if capability in self._capabilities_index:
                    self._capabilities_index[capability].remove(agent_id)
                    if not self._capabilities_index[capability]:
                        del self._capabilities_index[capability]

            del self._agents[agent_id]
            logger.info(f"Unregistered agent {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID.

        Args:
            agent_id: ID of the agent to get

        Returns:
            The agent, or None if not found
        """
        return self._agents.get(agent_id)

    def list_agents(self) -> list:
        """List all registered agents.

        Returns:
            List of agent info dictionaries
        """
        return [agent.get_info() for agent in self._agents.values()]

    def find_by_capability(self, capability: str) -> list:
        """Find agents that have a specific capability.

        Args:
            capability: The capability to search for

        Returns:
            List of agent info dictionaries
        """
        agent_ids = self._capabilities_index.get(capability, [])
        return [
            self._agents[agent_id].get_info()
            for agent_id in agent_ids
            if agent_id in self._agents
        ]

    def clear(self) -> None:
        """Clear all registered agents."""
        self._agents.clear()
        self._capabilities_index.clear()
