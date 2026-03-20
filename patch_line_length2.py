import re

# Fix src/agents_protocol/agents.py:199
with open("src/agents_protocol/agents.py", "r") as f:
    content = f.read()

content = content.replace(
    '                    f"Message loop crashed for agent {self.agent_id}: {task.exception()}"',
    '                    f"Message loop crashed for agent {self.agent_id}: "\n                    f"{task.exception()}"'
)

with open("src/agents_protocol/agents.py", "w") as f:
    f.write(content)

# Fix src/agents_protocol/messaging.py:181
with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace(
    '                # Direct message - If recipient is local, bypass the router for performance',
    '                # Direct message - If recipient is local, bypass router for performance'
)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
