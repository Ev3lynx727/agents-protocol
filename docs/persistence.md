# Message Persistence

The `agents_protocol` supports persistent message storage to enable history tracking, delivery guarantees, and auditing.

## 1. SQLite Message Store

By default, an in-memory or SQLite-based store can be used.

### Store Configuration

```python
from agents_protocol.persistence import SQLiteMessageStore

# In-memory store
store = SQLiteMessageStore(":memory:")

# File-based store
store = SQLiteMessageStore("messages.db")

broker = MessageBroker(store=store)
```

## 2. Message History

Query historic messages for any agent.

### Usage

```python
history = await broker.get_history("agent_1", limit=50)
for msg in history:
    print(f"{msg.timestamp}: {msg.content}")
```

## 3. Dead Letter Queue (DLQ)

Messages that fail to deliver are automatically placed in the DLQ for inspection and manual resolution.

### Accessing DLQ

```python
dlq_messages = await store.get_dlq_messages()
for entry in dlq_messages:
    print(f"Failed Message ID: {entry['message_id']}, Error: {entry['error']}")
```

## 4. Message Replay

Re-attempt delivery for messages stored in the DLQ.

### Replay Usage

```python
# Replay a specific message
success = await broker.replay_message("failed-message-id")
```
