import re

with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("await ws.send(message.json())", "await ws.send(message.model_dump_json())")

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
