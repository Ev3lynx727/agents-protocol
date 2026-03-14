import re

with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

# Fix timeout manager call
content = content.replace(
    "await self.timeout_manager.run_with_timeout(\n                    self.retry_policy.execute, args=(_send,)\n                ),",
    "await self.timeout_manager.run_with_timeout(\n                    self.retry_policy.execute, self.timeout, _send\n                ),"
)

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
