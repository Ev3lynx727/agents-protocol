import re

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

# Fix _broadcast
replacement_broadcast = """                # Create a deep copy of the message for each recipient
                msg_copy = message.model_copy(deep=True, update={"recipient_id": agent_id})
                tasks.append(self._deliver_locally(agent_id, msg_copy))"""

content = re.sub(
    r'                # Create a copy of the message for each recipient\n                msg_copy = AgentMessage\(\n                    id=message\.id,\n                    type=message\.type,\n                    sender_id=message\.sender_id,\n                    recipient_id=agent_id,\n                    priority=message\.priority,\n                    status=message\.status,\n                    timestamp=message\.timestamp,\n                    correlation_id=message\.correlation_id,\n                    reply_to=message\.reply_to,\n                    content=message\.content\.copy\(\),\n                    metadata=message\.metadata\.copy\(\),\n                \)\n                tasks\.append\(self\._deliver_locally\(agent_id, msg_copy\)\)',
    replacement_broadcast,
    content,
    flags=re.MULTILINE
)

# Fix send (router multiple recipients)
replacement_send_tasks = """                    for rid in recipients:
                        tasks.append(self._deliver_locally(rid, msg.model_copy(deep=True, update={"recipient_id": rid})))"""

content = re.sub(
    r'                    for rid in recipients:\n                        tasks\.append\(self\._deliver_locally\(rid, msg\)\)',
    replacement_send_tasks,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
