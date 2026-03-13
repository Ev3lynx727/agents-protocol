import asyncio
import time
import logging
from agents_protocol import (
    MessageBroker,
    Agent,
    AgentMessage,
    MessageType,
    MessagePriority,
)

# Configure logging to be quiet during benchmark
logging.basicConfig(level=logging.ERROR)


class BenchmarkAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, f"Agent {agent_id}")
        self.received_priorities = []
        self.start_time = None
        self.end_time = None
        self.stop_event = asyncio.Event()
        # Register handler for all notification messages
        self.register_handler(MessageType.NOTIFICATION, self.handle_perf_message)

    async def handle_perf_message(self, message: AgentMessage) -> None:
        if self.start_time is None:
            self.start_time = time.perf_counter()

        # We don't want to spend too much time here
        self.received_priorities.append(message.priority)

        if message.content.get("action") == "STOP":
            self.end_time = time.perf_counter()
            self.stop_event.set()

        return None


async def run_benchmark(num_messages: int = 400):
    broker = MessageBroker()
    # We don't necessarily need a channel for local broker tests,
    # but we'll use it if we want to simulate full overhead.
    # For now, let's keep it simple.

    sender = Agent("sender", "Sender")
    receiver = BenchmarkAgent("receiver")

    await sender.connect(broker)
    await receiver.connect(broker)

    # To ensure queue saturation, let's TEMPORARILY stop the receiver's loop
    # or just send very fast.
    receiver._running = False  # Stop the loop
    await asyncio.sleep(0.1)

    print(f"Starting benchmark with {num_messages} messages...")

    # Send in blocks: LOW, NORMAL, HIGH, CRITICAL
    # If it's FIFO, we'll see them in this order.
    # If it's Priority, we'll see CRITICAL first.

    for p in [
        MessagePriority.LOW,
        MessagePriority.NORMAL,
        MessagePriority.HIGH,
        MessagePriority.CRITICAL,
    ]:
        for i in range(num_messages // 4):
            msg = AgentMessage(
                type=MessageType.NOTIFICATION,
                sender_id="sender",
                recipient_id="receiver",
                priority=p,
                content={"index": i},
            )
            await sender.send_message(msg)

    # Send STOP message with lowest priority
    stop_msg = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        recipient_id="receiver",
        priority=MessagePriority.LOW,
        content={"action": "STOP"},
    )
    await sender.send_message(stop_msg)

    print("Saturated queue. Starting consumer...")
    receiver._running = True
    asyncio.create_task(receiver._message_loop())

    try:
        await asyncio.wait_for(receiver.stop_event.wait(), timeout=15)
    except asyncio.TimeoutError:
        print(
            f"Benchmark timed out! Received "
            f"{len(receiver.received_priorities)} messages."
        )

    if receiver.end_time and receiver.start_time:
        total_duration = receiver.end_time - receiver.start_time
        throughput = num_messages / total_duration
        print("Results:")
        print(f"  Total processing duration: {total_duration:.4f}s")
        print(f"  Throughput: {throughput:.2f} msg/s")

        first_20 = receiver.received_priorities[:20]
        last_20 = receiver.received_priorities[-20:]
        print(f"  First 20 priorities: {first_20}")
        print(f"  Last 20 priorities: {last_20}")

        # Check if reordered
        if first_20[0] == MessagePriority.CRITICAL:
            print("SUCCESS: Priority was respected (CRITICAL messages received first).")
        elif first_20[0] == MessagePriority.LOW:
            print("FIFO: Messages received in send order (Priority IGNORED).")
        else:
            print(f"MIXED: First message priority was {first_20[0]}.")

    await sender.disconnect()
    await receiver.disconnect()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
