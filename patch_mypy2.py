with open("src/agents_protocol/persistence.py", "r") as f:
    content = f.read()

content = content.replace("from typing import List, Optional, Dict", "from typing import List, Optional, Dict, Any")

with open("src/agents_protocol/persistence.py", "w") as f:
    f.write(content)
