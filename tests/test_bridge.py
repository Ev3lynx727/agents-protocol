"""Tests for the agent bridge components."""

from __future__ import annotations

import pytest
import asyncio
import json
from agents_protocol import (
    MessageBroker,
    Agent,
    AgentMessage,
    MessageType,
    JSONRPCAdapter,
    StreamBridgeAgent,
    LocalChannel,
)


class MockOrchestrator(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Mock Orchestrator")
        self.responses = []
        self.register_handler(MessageType.RESPONSE, self.handle_response)

    async def handle_response(self, message: AgentMessage) -> None:
        self.responses.append(message)


@pytest.mark.asyncio
async def test_jsonrpc_adapter_translation():
    """Test that JSONRPCAdapter correctly translates messages."""
    adapter = JSONRPCAdapter()

    # JSON-RPC -> AgentMessage (Request)
    rpc_req = {
        "jsonrpc": "2.0",
        "method": "test_method",
        "params": {"a": 1},
        "id": "123",
    }
    internal_msg = adapter.to_protocol(rpc_req)
    assert internal_msg.type == MessageType.REQUEST
    assert internal_msg.content == {"method": "test_method", "params": {"a": 1}}
    assert internal_msg.correlation_id == "123"

    # AgentMessage -> JSON-RPC (Response)
    reply = internal_msg.create_reply({"result": "ok"})
    rpc_res = adapter.from_protocol(reply)
    assert rpc_res["jsonrpc"] == "2.0"
    assert rpc_res["id"] == "123"
    assert rpc_res["result"] == {"result": "ok"}


@pytest.mark.asyncio
async def test_bridge_agent_e2e():
    """Test end-to-end communication via StreamBridgeAgent."""
    broker = MessageBroker()
    channel = LocalChannel(broker)
    await channel.start()

    # 1. Setup a mock external service (Client B)
    external_received = []

    async def server_callback(reader, writer):
        line = await reader.readline()
        if line:
            data = json.loads(line.decode())
            external_received.append(data)
            # Respond back via JSON-RPC
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"echo": data.get("params")},
            }
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(server_callback, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    # 2. Start the Orchestrator
    orchestrator = MockOrchestrator("orchestrator")
    await orchestrator.connect(broker)

    # 3. Start the Bridge Agent
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    bridge = StreamBridgeAgent("bridge_b", "Bridge B", reader, writer)
    await bridge.connect(broker)

    try:
        # 4. Orchestrator sends request to Bridge
        req = AgentMessage(
            type=MessageType.REQUEST,
            sender_id="orchestrator",
            recipient_id="bridge_b",
            content={"method": "ping", "params": "hello"},
        )
        await orchestrator.send_message(req)

        # 5. Wait for message to reach external service and come back
        for _ in range(50):  # Wait up to 5 seconds
            if len(orchestrator.responses) >= 1:
                break
            await asyncio.sleep(0.1)

        # 6. Verify external received the JSON-RPC
        assert len(external_received) == 1
        assert external_received[0]["method"] == "ping"

        # 7. Verify orchestrator received the Response via protocol
        assert len(orchestrator.responses) == 1
        assert orchestrator.responses[0].content["echo"] == "hello"
        assert orchestrator.responses[0].correlation_id == req.id

    finally:
        await bridge.disconnect()
        await orchestrator.disconnect()
        await channel.stop()
        server.close()
        await server.wait_closed()
