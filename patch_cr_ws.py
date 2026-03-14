with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("import httpx\n        except ImportError:\n            raise ImportError(\n                \"websockets", "import websockets\n        except ImportError:\n            raise ImportError(\n                \"websockets")

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
