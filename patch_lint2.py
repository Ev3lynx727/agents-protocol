with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("import time\n", "import time\nimport itertools\n")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
