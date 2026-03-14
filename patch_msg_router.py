import re

with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

replacement = """
    def _match_pattern(self, pattern: str, message: AgentMessage) -> bool:
        \"\"\"Check if a message matches a routing pattern.

        Args:
            pattern: The pattern to match against
            message: The message to check

        Returns:
            True if the pattern matches
        \"\"\"
        # Simple pattern matching - can be extended
        if pattern.startswith("capability:"):
            return message.recipient_id == pattern
        return False
"""

content = re.sub(
    r'    def _match_pattern\(self, pattern: str, message: AgentMessage\) -> bool:\n(?:.*\n){10,18}        return False',
    replacement.strip("\n"),
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
