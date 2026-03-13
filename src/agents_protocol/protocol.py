"""Core protocol definitions for agent communication."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, model_validator
import uuid
from datetime import datetime, timezone


class MessageType(str, Enum):
    """Types of messages that can be exchanged between agents."""

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class MessagePriority(int, Enum):
    """Priority levels for messages."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class MessageStatus(str, Enum):
    """Status of a message in its lifecycle."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentMessage(BaseModel):
    """Standardized message format for agent communication.

    This is the core data structure that all agents use to communicate.
    It provides a consistent format that can be serialized/deserialized
    across different communication channels.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    sender_id: str
    recipient_id: Optional[str] = None  # None means broadcast
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None  # For request/response tracking
    reply_to: Optional[str] = None  # Message ID this is replying to
    content: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def set_correlation_id_if_none(self) -> "AgentMessage":
        """If no correlation_id, use the message id."""
        if self.correlation_id is None:
            self.correlation_id = self.id
        return self

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        """Deserialize message from JSON string."""
        return cls.model_validate_json(json_str)

    def create_reply(
        self, content: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None
    ) -> "AgentMessage":
        """Create a reply message to this one."""
        return AgentMessage(
            type=MessageType.RESPONSE,
            sender_id="",  # To be set by the responding agent
            recipient_id=self.sender_id,
            priority=self.priority,
            correlation_id=self.correlation_id,
            reply_to=self.id,
            content=content,
            metadata=metadata or {},
        )


class AgentProtocol:
    """Base protocol interface that all agents should implement.

    This defines the standard methods that agents need to support
    for communication using the agents_protocol.
    """

    async def send_message(self, message: AgentMessage) -> MessageStatus:
        """Send a message to another agent.

        Args:
            message: The message to send

        Returns:
            The status of the sent message
        """
        raise NotImplementedError("Agents must implement send_message")

    async def receive_message(self) -> Optional[AgentMessage]:
        """Receive a message from the agent's inbox.

        Returns:
            The received message, or None if no message available
        """
        raise NotImplementedError("Agents must implement receive_message")

    async def broadcast(self, message: AgentMessage) -> None:
        """Broadcast a message to all agents (if supported).

        Args:
            message: The message to broadcast
        """
        raise NotImplementedError(
            "Agents must implement broadcast if broadcasting is supported"
        )

    def get_agent_id(self) -> str:
        """Get the unique identifier for this agent."""
        raise NotImplementedError("Agents must implement get_agent_id")

    async def connect(self, broker: Any) -> None:
        """Establish connection to the communication network."""

    async def disconnect(self) -> None:
        """Disconnect from the communication network."""

    async def is_connected(self) -> bool:
        """Check if the agent is connected."""
        return True
