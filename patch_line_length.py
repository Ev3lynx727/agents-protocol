import re

# Fix src/agents_protocol/agents.py:199
with open("src/agents_protocol/agents.py", "r") as f:
    content = f.read()

content = content.replace(
    '                logger.error(f"Message loop crashed for agent {self.agent_id}: {task.exception()}")',
    '                logger.error(\n                    f"Message loop crashed for agent {self.agent_id}: "\n                    f"{task.exception()}"\n                )'
)

with open("src/agents_protocol/agents.py", "w") as f:
    f.write(content)

# Fix src/agents_protocol/messaging.py:181
with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace(
    '                        tasks.append(self._deliver_locally(rid, msg.model_copy(deep=True, update={"recipient_id": rid})))',
    '                        msg_copy = msg.model_copy(deep=True, update={"recipient_id": rid})\n                        tasks.append(self._deliver_locally(rid, msg_copy))'
)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
