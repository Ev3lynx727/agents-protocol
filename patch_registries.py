import re

# ChannelRegistry
with open("src/agents_protocol/channels.py", "r") as f:
    content = f.read()

replacement_channel = """
    @classmethod
    def clear(cls) -> None:
        cls._channels.clear()
        cls.register("local", LocalChannel)
        cls.register("http", HTTPChannel)
        cls.register("websocket", WebSocketChannel)
        cls.register("tcp", TCPSocketChannel)

    @classmethod
    def register(cls, name: str, channel_class: type[Channel]) -> None:"""

content = content.replace("    @classmethod\n    def register(cls, name: str, channel_class: type[Channel]) -> None:", replacement_channel)

with open("src/agents_protocol/channels.py", "w") as f:
    f.write(content)

# RouterRegistry
with open("src/agents_protocol/messaging.py", "r") as f:
    content = f.read()

replacement_router = """
    @classmethod
    def clear(cls) -> None:
        cls._routers.clear()
        cls.register("default", MessageRouter)

    @classmethod
    def register(cls, name: str, router_class: type[MessageRouter]) -> None:"""

content = content.replace("    @classmethod\n    def register(cls, name: str, router_class: type[MessageRouter]) -> None:", replacement_router)

with open("src/agents_protocol/messaging.py", "w") as f:
    f.write(content)
