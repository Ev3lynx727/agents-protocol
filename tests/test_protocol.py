"""Tests for the protocol module."""

from agents_protocol.protocol import (
    AgentMessage,
    MessageType,
    MessagePriority,
    MessageStatus,
)


def test_agent_message_creation():
    """Test creating a basic agent message."""
    message = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="agent1",
        recipient_id="agent2",
        content={"text": "Hello"},
    )

    assert message.type == MessageType.REQUEST
    assert message.sender_id == "agent1"
    assert message.recipient_id == "agent2"
    assert message.content == {"text": "Hello"}
    assert message.status == MessageStatus.PENDING
    assert message.id is not None
    assert message.correlation_id == message.id


def test_agent_message_serialization():
    """Test JSON serialization and deserialization."""
    original = AgentMessage(
        type=MessageType.RESPONSE,
        sender_id="agent1",
        recipient_id="agent2",
        content={"result": 42},
        metadata={"key": "value"},
    )

    json_str = original.to_json()
    restored = AgentMessage.from_json(json_str)

    assert restored.id == original.id
    assert restored.type == original.type
    assert restored.sender_id == original.sender_id
    assert restored.recipient_id == original.recipient_id
    assert restored.content == original.content
    assert restored.metadata == original.metadata


def test_agent_message_reply():
    """Test creating a reply message."""
    original = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="agent1",
        recipient_id="agent2",
        content={"query": "test"},
        correlation_id="corr-123",
    )

    reply = original.create_reply(
        content={"answer": "reply"}, metadata={"processed": True}
    )

    assert reply.type == MessageType.RESPONSE
    assert reply.sender_id == ""  # To be set by responding agent
    assert reply.recipient_id == "agent1"
    assert reply.correlation_id == "corr-123"
    assert reply.reply_to == original.id
    assert reply.content == {"answer": "reply"}
    assert reply.metadata == {"processed": True}


def test_message_priority_ordering():
    """Test message priority enum values."""
    assert MessagePriority.LOW < MessagePriority.NORMAL
    assert MessagePriority.NORMAL < MessagePriority.HIGH
    assert MessagePriority.HIGH < MessagePriority.CRITICAL
