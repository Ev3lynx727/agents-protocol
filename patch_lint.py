with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("import time\n", "import time\nimport itertools\n")
content = content.replace("import itertools\n", "", 1) # remove the one on line 23
content = content.replace("\n\nimport itertools\n", "\n")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
