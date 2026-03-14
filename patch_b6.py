import re

with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

replacement_init = """    def __init__(self) -> None:
        import collections
        # Maps message.id to AgentMessage
        self._messages: Dict[str, AgentMessage] = {}
        # Lists of message IDs partitioned by agent
        self._agent_history: Dict[str, collections.deque] = {}
        self._agent_history_sets: Dict[str, set] = {}
        # Maps correlation_id to lists of message IDs
        self._conversations: Dict[str, collections.deque] = {}
        self._conversation_sets: Dict[str, set] = {}
        # Dead Letter Queue
        self._dlq: Dict[str, Dict] = {}
        self.MAX_HISTORY = 1000"""

content = re.sub(
    r'    def __init__\(self\) -> None:\n        # Maps message\.id to AgentMessage\n        self\._messages: Dict\[str, AgentMessage\] = \{\}\n        # Lists of message IDs partitioned by agent\n        self\._agent_history: Dict\[str, List\[str\]\] = \{\}\n        # Maps correlation_id to lists of message IDs\n        self\._conversations: Dict\[str, List\[str\]\] = \{\}\n        # Dead Letter Queue: Dict\[message_id,\n        #   Dict\{"message": AgentMessage, "reason": str, "time": datetime\}\]\n        self\._dlq: Dict\[str, Dict\] = \{\}',
    replacement_init,
    content,
    flags=re.MULTILINE
)

replacement_save = """    def _add_to_history(self, history_dict, set_dict, key, msg_id):
        import collections
        if key not in history_dict:
            history_dict[key] = collections.deque(maxlen=self.MAX_HISTORY)
            set_dict[key] = set()
        if msg_id not in set_dict[key]:
            if len(history_dict[key]) == self.MAX_HISTORY:
                old_id = history_dict[key].popleft()
                set_dict[key].discard(old_id)
            history_dict[key].append(msg_id)
            set_dict[key].add(msg_id)

    async def save_message(self, message: AgentMessage) -> None:
        \"\"\"Save message to in-memory dictionaries.\"\"\"
        self._messages[message.id] = message

        # Track history for sender
        if message.sender_id:
            self._add_to_history(self._agent_history, self._agent_history_sets, message.sender_id, message.id)

        # Track history for recipient (if concrete)
        if message.recipient_id:
            self._add_to_history(self._agent_history, self._agent_history_sets, message.recipient_id, message.id)

        # Track by correlation_id for conversation tracking
        if message.correlation_id:
            self._add_to_history(self._conversations, self._conversation_sets, message.correlation_id, message.id)"""

content = re.sub(
    r'    async def save_message\(self, message: AgentMessage\) -> None:\n        """Save message to in-memory dictionaries\."""\n        self\._messages\[message\.id\] = message\n\n        # Track history for sender\n        if message\.sender_id:\n            if message\.sender_id not in self\._agent_history:\n                self\._agent_history\[message\.sender_id\] = \[\]\n            if message\.id not in self\._agent_history\[message\.sender_id\]:\n                self\._agent_history\[message\.sender_id\]\.append\(message\.id\)\n\n        # Track history for recipient \(if concrete\)\n        if message\.recipient_id:\n            if message\.recipient_id not in self\._agent_history:\n                self\._agent_history\[message\.recipient_id\] = \[\]\n            if message\.id not in self\._agent_history\[message\.recipient_id\]:\n                self\._agent_history\[message\.recipient_id\]\.append\(message\.id\)\n\n        # Track by correlation_id for conversation tracking\n        if message\.correlation_id:\n            if message\.correlation_id not in self\._conversations:\n                self\._conversations\[message\.correlation_id\] = \[\]\n            if message\.id not in self\._conversations\[message\.correlation_id\]:\n                self\._conversations\[message\.correlation_id\]\.append\(message\.id\)',
    replacement_save,
    content,
    flags=re.MULTILINE
)

# Fix get_history and get_conversation to handle deque
content = content.replace(
    "ids = self._agent_history[agent_id][-limit:]",
    "ids = list(self._agent_history[agent_id])[-limit:]"
)
content = content.replace(
    "ids = self._conversations[correlation_id]",
    "ids = list(self._conversations[correlation_id])"
)

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)
