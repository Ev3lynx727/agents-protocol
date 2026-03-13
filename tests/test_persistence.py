"""Tests for the persistence module."""

from __future__ import annotations

import pytest
from agents_protocol import (
    MessageBroker,
    AgentMessage,
    MessageType,
    MessageStatus,
    InMemoryMessageStore,
    Agent,
)


class DummyAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id=agent_id, name="Dummy")
        self.received = []

    async def handle_request(self, message: AgentMessage) -> dict:
        self.received.append(message)
        return {"status": "ok"}


@pytest.fixture
def store():
    return InMemoryMessageStore()


@pytest.fixture
def broker(store):
    return MessageBroker(store=store)


@pytest.mark.asyncio
async def test_store_saves_message_on_send(broker, store):
    """Test that messages sent through the broker are saved in the store."""
    agent1 = DummyAgent("agent1")
    agent2 = DummyAgent("agent2")
    await agent1.connect(broker)
    await agent2.connect(broker)

    msg = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="agent1",
        recipient_id="agent2",
        content={"data": "hello"},
    )

    await broker.send(msg)

    # Store should have the message
    saved_msg = await store.get_message(msg.id)
    assert saved_msg is not None
    assert saved_msg.id == msg.id
    assert saved_msg.content == {"data": "hello"}

    # Status should be DELIVERED since agent2 was connected
    assert saved_msg.status == MessageStatus.DELIVERED


@pytest.mark.asyncio
async def test_store_history_tracking(broker, store):
    """Test that message history is retrievable per-agent."""
    a1 = DummyAgent("a1")
    a2 = DummyAgent("a2")
    await a1.connect(broker)
    await a2.connect(broker)

    await broker.send(
        AgentMessage(
            type=MessageType.NOTIFICATION, sender_id="a1", recipient_id="a2", content={}
        )
    )
    await broker.send(
        AgentMessage(
            type=MessageType.NOTIFICATION, sender_id="a2", recipient_id="a1", content={}
        )
    )

    a1_history = await broker.get_history("a1")
    assert len(a1_history) == 2  # Sent one, received one

    a2_history = await store.get_history("a2")
    assert len(a2_history) == 2  # Received one, sent one


@pytest.mark.asyncio
async def test_store_conversations(broker, store):
    """Test correlation ID conversation tracking."""
    agent1 = DummyAgent("agent1")
    agent2 = DummyAgent("agent2")
    await agent1.connect(broker)
    await agent2.connect(broker)

    req = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="agent1",
        recipient_id="agent2",
        correlation_id="conv-123",
    )
    await broker.send(req)

    reply = req.create_reply({"result": True})
    reply.sender_id = "agent2"
    await broker.send(reply)

    convo = await store.get_conversation("conv-123")
    assert len(convo) == 2
    assert convo[0].id == req.id
    assert convo[1].id == reply.id


@pytest.mark.asyncio
async def test_dead_letter_queue_and_replay(broker, store):
    """Test that failed messages go to DLQ and can be replayed."""
    agent1 = DummyAgent("agent1")
    await agent1.connect(broker)

    # agent2 is NOT connected
    msg = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="agent1",
        recipient_id="agent2",
    )

    # Send fails and routes to DLQ natively internally
    status = await broker.send(msg)
    assert status == MessageStatus.FAILED

    # Check DLQ
    dlq = await store.get_dlq()
    assert len(dlq) == 1
    assert dlq[0]["message"].id == msg.id
    assert "Agent agent2 not registered" in dlq[0]["reason"]

    # Now connect agent2 so replay can succeed
    agent2 = DummyAgent("agent2")
    await agent2.connect(broker)

    # Replay it!
    success = await broker.replay_message(msg.id)
    assert success is True

    # Ensure it's removed from DLQ
    new_dlq = await store.get_dlq()
    assert len(new_dlq) == 0

    # Ensure it updated the store's canonical status
    saved_msg = await store.get_message(msg.id)
    assert saved_msg.status == MessageStatus.DELIVERED
