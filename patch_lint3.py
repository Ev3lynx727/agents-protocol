with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

content = content.replace("    \"\"\"Central message broker for routing messages between agents.", "class MessageBroker:\n    \"\"\"Central message broker for routing messages between agents.")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
