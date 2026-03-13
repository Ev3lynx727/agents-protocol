"""Tests for security enhancements including authentication and ACLs."""

from __future__ import annotations

import pytest
import asyncio
from agents_protocol import (
    MessageBroker, Agent, AgentMessage, MessageType, 
    SecurityManager, AuthStatus, MessageStatus
)


class MockAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, f"Agent {agent_id}")
        self.received = []

    async def _handle_message(self, message: AgentMessage) -> None:
        self.received.append(message)


@pytest.mark.asyncio
async def test_security_manager_authentication():
    """Test that SecurityManager correctly verifies agent tokens."""
    sm = SecurityManager()
    sm.register_agent_credentials("agent_1", "secret_token_123")

    # 1. Valid token
    msg_valid = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_1",
        security={"token": "secret_token_123"},
        content={"data": "hello"}
    )
    assert sm.verify_message(msg_valid) == AuthStatus.SUCCESS

    # 2. Invalid token
    msg_invalid = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_1",
        security={"token": "wrong_token"},
        content={"data": "hello"}
    )
    assert sm.verify_message(msg_invalid) == AuthStatus.UNAUTHORIZED

    # 3. Missing token for registered agent
    msg_missing = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_1",
        content={"data": "hello"}
    )
    assert sm.verify_message(msg_missing) == AuthStatus.UNAUTHORIZED

    # 4. Unregistered agent (defaults to success if no keys registered for it)
    msg_unregistered = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_x",
        content={"data": "hello"}
    )
    assert sm.verify_message(msg_unregistered) == AuthStatus.SUCCESS


@pytest.mark.asyncio
async def test_security_manager_acl():
    """Test standard ACL enforcement."""
    sm = SecurityManager()
    sm.set_acl("agent_1", ["agent_2", "agent_3"])

    # Allowed recipient
    msg_allowed = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_1",
        recipient_id="agent_2",
        content={"data": "hi"}
    )
    assert sm.verify_message(msg_allowed) == AuthStatus.SUCCESS

    # Blocked recipient
    msg_blocked = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="agent_1",
        recipient_id="agent_4",
        content={"data": "hi"}
    )
    assert sm.verify_message(msg_blocked) == AuthStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_broker_security_integration():
    """Test that MessageBroker uses SecurityManager to block unauthorized messages."""
    sm = SecurityManager()
    sm.register_agent_credentials("sender", "valid_token")
    
    broker = MessageBroker(security_manager=sm)
    
    sender = MockAgent("sender")
    receiver = MockAgent("receiver")
    await broker.register_agent(sender)
    await broker.register_agent(receiver)

    # 1. Send with valid token
    msg_ok = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        recipient_id="receiver",
        security={"token": "valid_token"},
        content={"ping": "pong"}
    )
    status_ok = await broker.send(msg_ok)
    assert status_ok == MessageStatus.DELIVERED
    
    # Consume the valid message
    got_ok = await broker.get_next_message_for_agent("receiver")
    assert got_ok is not None
    assert got_ok.id == msg_ok.id
    assert broker._agent_inboxes["receiver"].empty()
    
    # 2. Send with invalid token
    msg_bad = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        recipient_id="receiver",
        security={"token": "invalid"},
        content={"ping": "pong"}
    )
    status_bad = await broker.send(msg_bad)
    assert status_bad == MessageStatus.FAILED
    
    # Verify receiver's inbox is still empty
    assert broker._agent_inboxes["receiver"].empty()
