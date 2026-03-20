import re

with open("src/agents_protocol/agents.py", "r") as f:
    content = f.read()

# Fix fire-and-forget task
replacement = """        self._running = True
        # Start the message processing loop
        self._loop_task = asyncio.create_task(self._message_loop())

        def _handle_exception(task):
            if not task.cancelled() and task.exception():
                logger.error(f"Message loop crashed for agent {self.agent_id}: {task.exception()}")

        self._loop_task.add_done_callback(_handle_exception)

        logger.info(f"Agent {self.agent_id} connected to broker")
        await self._hooks.trigger(AgentHook.POST_CONNECT, self, broker)

    async def disconnect(self) -> None:
        \"\"\"Disconnect the agent from the broker.\"\"\"
        await self._hooks.trigger(AgentHook.PRE_DISCONNECT, self)
        self._running = False
        if hasattr(self, '_loop_task') and self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        if self._broker:"""

content = re.sub(
    r'        self\._running = True\n        # Start the message processing loop\n        asyncio\.create_task\(self\._message_loop\(\)\)\n        logger\.info\(f"Agent \{self\.agent_id\} connected to broker"\)\n        await self\._hooks\.trigger\(AgentHook\.POST_CONNECT, self, broker\)\n\n    async def disconnect\(self\) -> None:\n        """Disconnect the agent from the broker\."""\n        await self\._hooks\.trigger\(AgentHook\.PRE_DISCONNECT, self\)\n        self\._running = False\n        if self\._broker:',
    replacement,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/agents.py", "w") as f:
    f.write(content)
