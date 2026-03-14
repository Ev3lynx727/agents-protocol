import re

with open("src/agents_protocol/bridge.py", "r") as f:
    content = f.read()

content = content.replace("import json", "import json\nimport collections")
content = content.replace("        self._request_map: Dict[str, str] = {}  # msg_id -> sender_id", "        self._request_map: collections.OrderedDict[str, str] = collections.OrderedDict()  # msg_id -> sender_id")

replacement = """        if message.type == MessageType.REQUEST:
            self._request_map[message.id] = message.sender_id
            if len(self._request_map) > 1000:
                self._request_map.popitem(last=False)"""

content = content.replace("        if message.type == MessageType.REQUEST:\n            self._request_map[message.id] = message.sender_id", replacement)

with open("src/agents_protocol/bridge.py", "w") as f:
    f.write(content)
