"""Tests for the TCPSocketChannel."""

import pytest
import asyncio
import struct
from agents_protocol.messaging import MessageBroker
from agents_protocol.agents import Agent
from agents_protocol.protocol import AgentMessage, MessageType, MessageStatus
from agents_protocol.channels import TCPSocketChannel


class SimpleAgent(Agent):
    """Simple test agent."""

    def __init__(self, agent_id: str):
        super().__init__(agent_id, f"Agent {agent_id}")
        self.received_messages = []
        self.register_handler(MessageType.REQUEST, self.handle_request)
        self.register_handler(MessageType.NOTIFICATION, self.handle_notification)

    async def handle_request(self, message: AgentMessage) -> dict:
        """Handle request messages."""
        self.received_messages.append(message)
        return {"echo": message.content}

    async def handle_notification(self, message: AgentMessage) -> dict:
        """Handle notification messages."""
        self.received_messages.append(message)
        return {"acknowledged": True}


@pytest.mark.asyncio
async def test_tcp_channel_lifecycle():
    """Test starting and stopping the TCP channel."""
    broker = MessageBroker()
    # Try using port 0 so the OS assigns a random free port (good practice for tests)
    channel = TCPSocketChannel(broker, port=0)

    try:
        await channel.start()
        assert channel._running is True
        assert channel._server is not None
        assert channel._server.is_serving()
    finally:
        await channel.stop()

    assert channel._running is False
    assert len(channel._connections) == 0


@pytest.mark.asyncio
async def test_tcp_channel_message_delivery():
    """Test sending and receiving messages via TCP channel."""
    broker1 = MessageBroker()
    broker2 = MessageBroker()

    # Agent 1 (sender) uses broker 1
    agent1 = SimpleAgent("agent1")
    await agent1.connect(broker1)

    # Agent 2 (receiver) uses broker 2 and listens on a TCP channel
    agent2 = SimpleAgent("agent2")
    await agent2.connect(broker2)

    # Let OS pick a free port for receiver
    channel2 = TCPSocketChannel(broker2, host="127.0.0.1", port=0)
    await channel2.start()

    # Get the actual port assigned to receiver
    host, port = channel2._server.sockets[0].getsockname()
    destination = f"{host}:{port}"

    # Sender channel doesn't strictly need to start a server just to send,
    # but it needs to be "running"
    channel1 = TCPSocketChannel(broker1, host="127.0.0.1", port=0)
    await channel1.start()

    try:
        # Create message from agent1 to agent2
        original_msg = AgentMessage(
            type=MessageType.NOTIFICATION,
            sender_id="agent1",
            recipient_id="agent2",
            content={"test": "tcp_data"},
        )

        # Agent 1 sends via channel 1 directly to Agent 2's destination
        status = await channel1.send(original_msg, destination)
        assert status == MessageStatus.DELIVERED

        # Wait a moment for network transmission and broker routing
        await asyncio.sleep(0.3)

        # Check agent2 received the message
        assert len(agent2.received_messages) > 0
        received_msg = agent2.received_messages[0]
        assert received_msg is not None
        assert received_msg.type == MessageType.NOTIFICATION
        assert received_msg.content == {"test": "tcp_data"}
        assert received_msg.sender_id == "agent1"
        assert received_msg.recipient_id == "agent2"

    finally:
        # Clean up
        await channel1.stop()
        await channel2.stop()


@pytest.mark.asyncio
async def test_tcp_channel_raw_read():
    """Test raw length-prefixed framing by connecting socket to channel."""
    broker = MessageBroker()
    agent = SimpleAgent("agent")
    await agent.connect(broker)

    channel = TCPSocketChannel(broker, host="127.0.0.1", port=0)
    await channel.start()

    try:
        host, port = channel._server.sockets[0].getsockname()
        if host == "0.0.0.0":
            host = "127.0.0.1"

        # Connect raw socket using asyncio directly
        reader, writer = await asyncio.open_connection(host, port)

        try:
            # Craft raw payload
            msg = AgentMessage(
                type=MessageType.NOTIFICATION,
                sender_id="test_raw",
                recipient_id="agent",
                content={"key": "val"},
            )
            payload = msg.json().encode()

            # Pack 4-byte big-endian header
            header = struct.pack(">I", len(payload))

            # Send
            writer.write(header + payload)
            await writer.drain()

            # Wait for broker
            await asyncio.sleep(0.3)

            # Verify handler processed it
            assert len(agent.received_messages) == 1
            assert agent.received_messages[0].sender_id == "test_raw"
            assert agent.received_messages[0].content == {"key": "val"}

        finally:
            writer.close()
            await writer.wait_closed()

    finally:
        await channel.stop()
