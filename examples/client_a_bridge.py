"""Example of a Bridge Client (Client A) using agents_protocol.

This script acts as "Client A" (e.g., an Orchestrator) that communicates
with "Client B" (the coding agent) via the agents_protocol bridge.
"""

from __future__ import annotations

import asyncio
import logging
from agents_protocol import Agent, MessageBroker, LocalChannel, AgentMessage, MessageType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestratorAgent(Agent):
    """A client agent that sends tasks to specialized bridge agents."""

    def __init__(self, agent_id: str):
        super().__init__(agent_id, "Orchestrator")
        self.received_responses = []
        self.register_handler(MessageType.RESPONSE, self.handle_response)

    async def handle_response(self, message: AgentMessage) -> None:
        logger.info(f"Orchestrator received response: {message.content}")
        self.received_responses.append(message)


async def main():
    # 1. Setup broker (In a real scenario, this broker would be on a server)
    broker = MessageBroker()
    channel = LocalChannel(broker)
    await channel.start()

    # 2. Start Client A (Orchestrator)
    orchestrator = OrchestratorAgent("client_a")
    await orchestrator.connect(broker)
    logger.info("Client A (Orchestrator) is online.")

    # 3. Note: This example assumes client_b_bridge.py is running in another
    # process or we have already registered a BridgeAgent in this broker.
    # For this demo, let's just send a message and see it fail (or wait).
    
    # Let's simulate that Client B is registered via our protocol
    # In a real multi-process scenario, Client B would connect via TCPSocketChannel
    
    print("\n--- Scenario: Client A sends a 'ping' task to Client B (Bridge) ---")
    
    task = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="client_a",
        recipient_id="client_b",  # Target the bridge agent
        content={"method": "ping", "params": {"payload": "bridge_test_123"}}
    )
    
    await orchestrator.send_message(task)
    logger.info("Task sent to 'client_b' via bridge.")

    # Since we need a running Client B for success, this example is meant to be
    # run alongside client_b_bridge.py if they share a broker.
    # To make this demo self-contained, we'll just log and exit.
    
    print("\nNOTE: Run 'examples/client_b_bridge.py' to see the full interaction.")
    await asyncio.sleep(1)

    await orchestrator.disconnect()
    await channel.stop()


if __name__ == "__main__":
    asyncio.run(main())
