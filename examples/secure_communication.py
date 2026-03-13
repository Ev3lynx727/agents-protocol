"""Example demonstrating secure agent communication with authentication and ACLs."""

import asyncio
import logging
from agents_protocol import (
    MessageBroker, Agent, AgentMessage, MessageType,
    SecurityManager, AuthStatus, LocalChannel
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class SecureAgent(Agent):
    """An agent that handles messages only if they are authenticated."""
    
    def __init__(self, agent_id: str, name: str, token: str):
        super().__init__(agent_id, name)
        self.token = token
        self.received_count = 0
        self.register_handler(MessageType.NOTIFICATION, self.on_notification)

    async def on_notification(self, message: AgentMessage) -> None:
        logger.info(f"[{self.name}] Received: {message.content}")
        self.received_count += 1

    async def send_secure(self, recipient_id: str, content: dict):
        """Send a message with our authentication token."""
        msg = AgentMessage(
            type=MessageType.NOTIFICATION,
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            content=content,
            security={"token": self.token}  # Attach token
        )
        return await self.send_message(msg)


async def main():
    # 1. Setup Security Manager
    sm = SecurityManager()
    
    # Register credentials for our agents
    sm.register_agent_credentials("orchestrator", "orch_secret_123")
    sm.register_agent_credentials("worker_a", "worker_secret_456")
    
    # Set ACLs: Orchestrator can message anyone, but workers can only message orchestrator
    sm.set_acl("orchestrator", ["*"])
    sm.set_acl("worker_a", ["orchestrator"])

    # 2. Setup Broker with Security
    broker = MessageBroker(security_manager=sm)
    channel = LocalChannel(broker)
    await channel.start()

    # 3. Initialize Agents
    orchestrator = SecureAgent("orchestrator", "Orchestrator", "orch_secret_123")
    worker_a = SecureAgent("worker_a", "Worker A", "worker_secret_456")
    worker_b = SecureAgent("worker_b", "Worker B", "no_key") # Not registered in SM

    await orchestrator.connect(broker)
    await worker_a.connect(broker)
    await worker_b.connect(broker)

    try:
        logger.info("--- Scenario 1: Authorized Communication ---")
        # Orchestrator sends task to Worker A
        await orchestrator.send_secure("worker_a", {"task": "process_data"})
        await asyncio.sleep(0.1)

        logger.info("\n--- Scenario 2: Unauthorized Token ---")
        # Worker A tries to send message with wrong token
        msg_bad_token = AgentMessage(
            type=MessageType.NOTIFICATION,
            sender_id="worker_a",
            recipient_id="orchestrator",
            content={"status": "done"},
            security={"token": "WRONG_TOKEN"}
        )
        status = await worker_a.send_message(msg_bad_token)
        logger.info(f"Message status with bad token: {status}")

        logger.info("\n--- Scenario 3: ACL Violation ---")
        # Worker A tries to message Worker B (not in ACL)
        status = await worker_a.send_secure("worker_b", {"hello": "there"})
        logger.info(f"Message status with ACL violation: {status}")

        logger.info("\n--- Scenario 4: Global ACL Allowance ---")
        # Orchestrator messages Worker B (Allowed by "*")
        await orchestrator.send_secure("worker_b", {"status": "shutdown"})
        await asyncio.sleep(0.1)

    finally:
        await orchestrator.disconnect()
        await worker_a.disconnect()
        await worker_b.disconnect()
        await channel.stop()


if __name__ == "__main__":
    asyncio.run(main())
