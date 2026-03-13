# Security in Agents Protocol

The `agents_protocol` provides built-in mechanisms for ensuring secure communication between agents.

## 1. Authentication

The `SecurityManager` manages agent identities and authentication tokens.

### Auth Configuration

```python
from agents_protocol.security import SecurityManager

security_manager = SecurityManager()
security_manager.add_agent("agent_1", "secret-token-1")

broker = MessageBroker(security_manager=security_manager)
```

## 2. Message Encryption

Message content can be encrypted using AES-GCM for secure transport over untrusted channels.

### Setup

```python
from agents_protocol.security import SecurityManager

# Initialize with a master key
key = b"sixteen-byte-key"
security_manager = SecurityManager(master_key=key)

# Content will be automatically encrypted/decrypted if encryption is enabled
message = AgentMessage(
    sender_id="agent_1",
    content={"secret": "highly-confidential"},
    metadata={"encrypt": True}
)
```

## 3. Access Control Lists (ACL)

Control which agents are allowed to send messages to whom.

### Configuration

```python
security_manager.add_acl_rule(
    sender_id="trusted_agent",
    recipient_id="sensitive_agent",
    allowed=True
)

security_manager.add_acl_rule(
    sender_id="untrusted_agent",
    recipient_id="*",
    allowed=False
)
```

## 4. Best Practices

- Always use `HTTPS` or `WSS` for network channels.
- Rotate authentication tokens regularly.
- Keep the `master_key` secure and never hardcode it in production.
- Use explicit ACL rules for sensitive agents.
