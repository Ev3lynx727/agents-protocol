import re

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("_, _, msg = priority_entry", "_, _, _, msg = priority_entry")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
