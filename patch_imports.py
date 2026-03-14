import re

with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("from __future__ import annotations", "from __future__ import annotations\nimport json\nimport httpx\nimport websockets")
content = content.replace("            import httpx\n", "")
content = content.replace("                import json\n\n", "")
content = content.replace("            import websockets\n", "")
content = content.replace("            import json\n\n", "")
content = content.replace("                import json\n\n", "")

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("from __future__ import annotations", "from __future__ import annotations\nimport time")
content = content.replace("            import time\n\n", "")
content = content.replace("self._agent_inboxes[agent_id] = asyncio.PriorityQueue()", "self._agent_inboxes[agent_id] = asyncio.PriorityQueue(maxsize=10000)")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)

with open("src/agents_protocol/cluster.py", "r") as f:
    content = f.read()

content = content.replace("        import uuid\n\n", "")
content = content.replace("from __future__ import annotations\nimport httpx", "from __future__ import annotations\nimport httpx\nimport uuid")

with open("src/agents_protocol/cluster.py", "w") as f:
    f.write(content)
