"""Example of a Bridge Agent (Client B) using agents_protocol.

This script simulates an external agent that communicates via JSON-RPC.
The StreamBridgeAgent wraps a TCP connection to this external system
and allows it to participate in the agents_protocol ecosystem.
"""

from __future__ import annotations

import asyncio
import json
import logging
from agents_protocol import MessageBroker, TCPSocketChannel, StreamBridgeAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def simulate_external_client_b(port: int):
    """Simulates an external system (Client B) that only speaks JSON-RPC."""
    server = await asyncio.start_server(handle_client, '127.0.0.1', port)
    logger.info(f"External Client B simulated service started on port {port}")
    async with server:
        await server.serve_forever()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle incoming JSON-RPC requests for Client B."""
    while True:
        line = await reader.readline()
        if not line:
            break
        
        try:
            request = json.loads(line.decode())
            logger.info(f"Client B (External) received: {request}")
            
            # Simple Echo/Response logic
            if request.get("method") == "ping":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {"status": "pong", "echo": request.get("params")}
                }
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
        except Exception as e:
            logger.error(f"Client B simulation error: {e}")


async def main():
    # 1. Start the simulation of external Client B (JSON-RPC only)
    # Typically this would be a separate process like OpenCode
    port = 8888
    asyncio.create_task(simulate_external_client_b(port))
    await asyncio.sleep(1)

    # 2. Setup agents_protocol infrastructure
    broker = MessageBroker()
    
    # 3. Create the Bridge Agent for Client B
    # Connect to the external process/service
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    
    bridge_b = StreamBridgeAgent(
        agent_id="client_b",
        name="Bridge to Client B",
        reader=reader,
        writer=writer,
        capabilities=["coding", "executor"]
    )
    
    await bridge_b.connect(broker)
    logger.info("Bridge for Client B is now online in the protocol.")

    # 4. Stay online to handle messages
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bridge_b.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
