import re

with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

# Fix HTTP body double-counting
content = content.replace(
    "            if content_length > 0:\n                body += await reader.readexactly(content_length)",
    "            remaining = content_length - len(body)\n            if remaining > 0:\n                body += await reader.readexactly(remaining)"
)

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
