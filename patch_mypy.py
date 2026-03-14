import re

# Fix src/agents_protocol/agents.py:196
with open("src/agents_protocol/agents.py", "r") as f:
    content = f.read()

content = content.replace(
    '        def _handle_exception(task):',
    '        def _handle_exception(task: asyncio.Task) -> None:'
)

with open("src/agents_protocol/agents.py", "w") as f:
    f.write(content)

# Fix src/agents_protocol/persistence.py:78
with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

content = content.replace(
    '    def _add_to_history(self, history_dict, set_dict, key, msg_id):',
    '    def _add_to_history(self, history_dict: Dict[str, Any], set_dict: Dict[str, set], key: str, msg_id: str) -> None:'
)

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)
