with open("src/agents_protocol/cluster.py", "r") as f:
    content = f.read()

content = content.replace("import httpx\n", "", 1)
content = content.replace("from __future__ import annotations", "from __future__ import annotations\nimport httpx")

with open("src/agents_protocol/cluster.py", "w") as f:
    f.write(content)
