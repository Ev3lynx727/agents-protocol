"""Tests for the agents module."""

import pytest
from typing import Dict, Any, Optional
from agents_protocol.agents import Agent, AgentRegistry
from agents_protocol.protocol import (
    AgentMessage,
    MessageType,
)


class MockAgent(Agent):
    """Test agent implementation."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            agent_id,
            name,
            capabilities=capabilities or ["test"],
            metadata=metadata or {},
        )
        self.received_messages = []
        self.register_handler(MessageType.REQUEST, self.handle_request)

    async def handle_request(self, message: AgentMessage) -> dict:
        """Handle request messages."""
        self.received_messages.append(message)
        return {"status": "received", "message_id": message.id}

    async def handle_notification(self, message: AgentMessage) -> None:
        """Handle notification messages."""
        self.received_messages.append(message)


@pytest.mark.asyncio
async def test_agent_creation():
    """Test creating an agent."""
    agent = MockAgent("test-agent-1", "Test Agent")
    assert agent.agent_id == "test-agent-1"
    assert agent.name == "Test Agent"
    assert "test" in agent.capabilities
    assert agent.get_agent_id() == "test-agent-1"


@pytest.mark.asyncio
async def test_agent_info():
    """Test getting agent info."""
    agent = MockAgent("test-agent-2", "Test Agent 2", metadata={"version": "1.0"})
    info = agent.get_info()
    assert info["agent_id"] == "test-agent-2"
    assert info["name"] == "Test Agent 2"
    assert "test" in info["capabilities"]
    assert info["metadata"]["version"] == "1.0"


@pytest.mark.asyncio
async def test_agent_registry():
    """Test the agent registry."""
    registry = AgentRegistry()
    agent1 = MockAgent("agent1", "Agent 1")
    agent2 = MockAgent("agent2", "Agent 2", capabilities=["special"])

    registry.register(agent1)
    registry.register(agent2)

    # Test listing agents
    agents = registry.list_agents()
    assert len(agents) == 2

    # Test finding by capability
    test_agents = registry.find_by_capability("test")
    assert len(test_agents) == 1  # Only agent1 has test capability
    assert test_agents[0]["agent_id"] == "agent1"

    special_agents = registry.find_by_capability("special")
    assert len(special_agents) == 1
    assert special_agents[0]["agent_id"] == "agent2"

    # Test getting specific agent
    retrieved = registry.get_agent("agent1")
    assert retrieved is agent1

    # Test unregistering
    registry.unregister("agent1")
    assert len(registry.list_agents()) == 1
    assert registry.get_agent("agent1") is None


@pytest.mark.asyncio
async def test_agent_handler_registration():
    """Test registering message handlers."""
    agent = MockAgent("test-agent-3", "Test Agent 3")

    # Handler should be registered for REQUEST
    assert MessageType.REQUEST in agent._message_handlers

    # Custom handler
    async def custom_handler(message: AgentMessage) -> dict:
        return {"custom": True}

    agent.register_handler(MessageType.NOTIFICATION, custom_handler)
    assert MessageType.NOTIFICATION in agent._message_handlers
