import re

with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

content = content.replace("        self._connections: set[asyncio.Task] = set()", "        self._connections: set[asyncio.Task] = set()\n        self._outgoing_connections: Dict[str, asyncio.StreamWriter] = {}")

stop_replacement = """    async def stop(self) -> None:
        \"\"\"Stop the TCP server and close any active background handler tasks.\"\"\"
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        for writer in self._outgoing_connections.values():
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        self._outgoing_connections.clear()"""

content = re.sub(
    r'    async def stop\(self\) -> None:\n        """Stop the TCP server and close any active background handler tasks\."""\n        if self\._server:\n            self\._server\.close\(\)\n            await self\._server\.wait_closed\(\)',
    stop_replacement,
    content,
    flags=re.MULTILINE
)

send_replacement = """        try:
            writer = self._outgoing_connections.get(destination)
            if not writer or writer.is_closing():
                reader, writer = await asyncio.open_connection(
                    host, port, ssl=self.ssl_context
                )
                self._outgoing_connections[destination] = writer

            data = message.model_dump_json().encode()
            # Big-endian 4-byte unsigned integer indicating length
            msg_length = struct.pack(">I", len(data))

            writer.write(msg_length + data)
            await writer.drain()
            message.status = MessageStatus.DELIVERED
            return message.status"""

content = re.sub(
    r'        try:\n            # We open a temporary connection for sending\.\n            reader, writer = await asyncio\.open_connection\(\n                host, port, ssl=self\.ssl_context\n            \)\n\n            try:\n                data = message\.model_dump_json\(\)\.encode\(\)\n                # Big-endian 4-byte unsigned integer indicating length\n                msg_length = struct\.pack\(">I", len\(data\)\)\n\n                writer\.write\(msg_length \+ data\)\n                await writer\.drain\(\)\n                message\.status = MessageStatus\.DELIVERED\n            finally:\n                writer\.close\(\)\n                await writer\.wait_closed\(\)\n\n            return message\.status',
    send_replacement,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)
