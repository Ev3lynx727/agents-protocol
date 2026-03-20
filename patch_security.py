import re

with open("src/agents_protocol/security.py", "r") as f:
    content = f.read()

content = content.replace("import ssl\nimport logging", "import ssl\nimport logging\nimport hmac")

content = content.replace(
    "            if token != expected_token:",
    "            if not hmac.compare_digest(token or '', expected_token):"
)

with open("src/agents_protocol/security.py", "w") as f:
    f.write(content)
