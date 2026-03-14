import re

with open("src/agents_protocol/extensions.py", "r") as f:
    content = f.read()

content = content.replace("import asyncio\n", "")
content = "import asyncio\n" + content

replacement = """    async def trigger(self, hook: AgentHook, *args: Any, **kwargs: Any) -> None:
        \"\"\"Trigger all callbacks for a hook.\"\"\"
        if self._hooks[hook]:
            await asyncio.gather(*(callback(*args, **kwargs) for callback in self._hooks[hook]))"""

content = re.sub(
    r'    async def trigger\(self, hook: AgentHook, \*args: Any, \*\*kwargs: Any\) -> None:\n        """Trigger all callbacks for a hook\."""\n        for callback in self\._hooks\[hook\]:\n            await callback\(\*args, \*\*kwargs\)',
    replacement,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/extensions.py", "w") as f:
    f.write(content)
