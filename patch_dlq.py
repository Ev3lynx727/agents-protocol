import re

with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

content = content.replace("from datetime import datetime", "from datetime import datetime\nimport heapq")

replacement = """    async def get_dlq(self, limit: int = 100) -> List[Dict]:
        \"\"\"Get the top $limit items from the DLQ dict, ordered chronologically.\"\"\"
        return heapq.nlargest(limit, self._dlq.values(), key=lambda x: x["failed_at"])"""

content = re.sub(
    r'    async def get_dlq\(self, limit: int = 100\) -> List\[Dict\]:\n        """Get the top \$limit items from the DLQ dict, ordered chronologically\."""\n        items = list\(self\._dlq\.values\(\)\)\n        # Sort by failed_at timestamp \(ascending\)\n        items\.sort\(key=lambda x: x\["failed_at"\]\)\n        return items\[-limit:\]',
    replacement,
    content,
    flags=re.MULTILINE
)

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)
