with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("        try:\n        except ImportError:", "        try:\n            import httpx\n        except ImportError:")

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
