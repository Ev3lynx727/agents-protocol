"""Basic example of using agents_protocol."""

import asyncio
from agents_protocol import (
    Agent, AgentMessage, MessageType, MessageBroker, LocalChannel
)


class EchoAgent(Agent):
    """Simple echo agent that responds to requests."""

    def __init__(self, agent_id: str, name: str):
        super().__init__(agent_id, name, capabilities=["echo"])
        self.register_handler(MessageType.REQUEST, self.handle_echo)

    async def handle_echo(self, message: AgentMessage) -> dict:
        """Echo back the received content with a greeting."""
        received = message.content.get("text", "")
        return {
            "echo": received,
            "from": self.agent_id,
            "message": f"Echo: {received}"
        }


async def main():
    # Create broker and channel
    broker = MessageBroker()
    channel = LocalChannel(broker)

    # Create agents
    alice = EchoAgent("alice", "Alice")
    bob = EchoAgent("bob", "Bob")

    # Connect agents to broker
    await alice.connect(broker)
    await bob.connect(broker)

    # Start the channel
    await channel.start()

    print("Agents connected and channel started!")

    # Alice sends a message to Bob
    message = AgentMessage(
        type=MessageType.REQUEST,
        sender_id="alice",
        recipient_id="bob",
        content={"text": "Hello, Bob!"}
    )

    print(f"Alice sending: {message.content}")
    await alice.send_message(message)

    # Wait for Bob to process and respond
    await asyncio.sleep(0.2)

    # Alice receives Bob's response
    response = await alice.receive_message()
    if response:
        print(f"Alice received response: {response.content}")
    else:
        print("No response received")

    # Try a broadcast
    print("\nSending broadcast from Alice...")
    broadcast = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="alice",
        recipient_id=None,  # Broadcast to all
        content={"announcement": "I'm online!"}
    )

    await alice.broadcast(broadcast)
    await asyncio.sleep(0.2)

    # Check if Bob received the broadcast
    bob_received = await bob.receive_message()
    if bob_received:
        print(f"Bob received broadcast: {bob_received.content}")

    # Clean up
    await alice.disconnect()
    await bob.disconnect()
    await channel.stop()
    print("\nAgents disconnected and channel stopped.")


if __name__ == "__main__":
    asyncio.run(main())