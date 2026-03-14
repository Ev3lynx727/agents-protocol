with open("src/agents_protocol/extensions.py", "r") as f:
    content = f.read()

content = content.replace("import asyncio\n", "", 1)
content = content.replace("from __future__ import annotations", "from __future__ import annotations\nimport asyncio")

with open("src/agents_protocol/extensions.py", "w") as f:
    f.write(content)
