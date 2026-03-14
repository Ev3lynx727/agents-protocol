with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

replacement = """    def _add_to_history(
        self,
        history_dict: Dict[str, Any],
        set_dict: Dict[str, set],
        key: str,
        msg_id: str,
    ) -> None:"""

content = content.replace("    def _add_to_history(self, history_dict: Dict[str, Any], set_dict: Dict[str, set], key: str, msg_id: str) -> None:", replacement)

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)
