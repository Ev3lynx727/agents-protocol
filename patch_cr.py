import re

# Fix NameError '_' in messaging.py
with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("await self.send(_)", "await self.send(msg)")
content = content.replace("_ = AgentMessage(", "msg = AgentMessage(")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)

# Fix order of get_dlq back to chronological
with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

content = content.replace('        return heapq.nlargest(limit, self._dlq.values(), key=lambda x: x["failed_at"])', '        items = heapq.nlargest(limit, self._dlq.values(), key=lambda x: x["failed_at"])\n        items.sort(key=lambda x: x["failed_at"])\n        return items')

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)

# Revert inline imports in channels.py to maintain optional dependencies
with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("from __future__ import annotations\nimport json\nimport httpx\nimport websockets", "from __future__ import annotations")

# Restore httpx import in HTTPChannel.start()
content = content.replace(
"""    async def start(self) -> None:
        \"\"\"Start the HTTP server.\"\"\"
        try:
            import httpx
        except ImportError:""",
"""    async def start(self) -> None:
        \"\"\"Start the HTTP server.\"\"\"
        try:
            import httpx
        except ImportError:"""
)

# Restore websockets import in WebSocketChannel.start()
content = content.replace(
"""    async def start(self) -> None:
        \"\"\"Start the WebSocket server.\"\"\"
        try:
        except ImportError:""",
"""    async def start(self) -> None:
        \"\"\"Start the WebSocket server.\"\"\"
        try:
            import websockets
        except ImportError:"""
)

# Re-add import json to _handle_request, handle_connection, and _process_stream
# and fix remaining missing inline imports in channels.py
# Actually, the quickest way to fix the missing imports in functions is to just let them be at module level for json, but remove httpx and websockets from module level.
# So I'll put import json back at top, but remove httpx and websockets, and put them back in the start methods.

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

# Make sure json is imported
if "import json" not in content:
    content = content.replace("import asyncio", "import asyncio\nimport json")

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
