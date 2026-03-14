import re

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

replacement = """            else:
                # Direct message - If recipient is local, bypass the router for performance
                if msg.recipient_id in self._agents:
                    await self._deliver_locally(msg.recipient_id, msg)
                    return msg.status

                # Still consult router for multiple recipients
                # (e.g. if recipient_id is a capability pattern)
                recipients = self._router.route(msg, list(self._agents.keys()))"""

content = re.sub(
    r'            else:\n                # Direct message - Still consult router for multiple recipients\n                # \(e\.g\. if recipient_id is a capability pattern\)\n                recipients = self\._router\.route\(msg, list\(self\._agents\.keys\(\)\)\)',
    replacement,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
