import re

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

# Replace Broker.request runtime error
replacement = """
        try:
            await self.send(_)
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self._pending_messages.pop(correlation_id, None)
            return None
        finally:
            self._pending_messages.pop(correlation_id, None)
"""

content = re.sub(
    r'        try:\n            # The actual send will be done by the agent\n            # This method is meant to be called by an agent\n            # So we need to set the sender_id properly\n            raise RuntimeError\(\n                "Broker\.request\(\) should not be called directly\. "\n                "Use agent\.send_request\(\) instead\."\n            \)\n        finally:\n            # Cleanup if needed\n            pass',
    replacement.strip("\n"),
    content,
    flags=re.MULTILINE
)

# Use itertools.count() for priority queues
content = content.replace("class MessageBroker:", "import itertools\n\nclass MessageBroker:")
content = content.replace("        self._extensions = ExtensionManager()", "        self._extensions = ExtensionManager()\n        self._counter = itertools.count()")
content = content.replace("            priority_entry = (-message.priority, time.time_ns(), message)", "            priority_entry = (-message.priority, time.time_ns(), next(self._counter), message)")

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
