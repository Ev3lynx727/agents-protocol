# Extension Points

The `agents_protocol` is designed to be highly extensible, allowing you to customize its behavior at multiple levels.

## 1. Agent Lifecycle Hooks

Inject logic at critical points in an agent's lifecycle.

### Available Hooks

- `PRE_CONNECT` / `POST_CONNECT`
- `PRE_DISCONNECT` / `POST_DISCONNECT`
- `PRE_MESSAGE_PROCESS` / `POST_MESSAGE_PROCESS`

### Usage

```python
from agents_protocol.extensions import AgentHook

async def my_hook(agent, *args):
    print(f"Agent {agent.agent_id} hook triggered!")

agent.register_hook(AgentHook.PRE_CONNECT, my_hook)
```

## 2. Broker Middleware

Intercept and transform all messages passing through the `MessageBroker`.

### Middleware Usage

```python
from agents_protocol.extensions import BaseMiddleware

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, message, next_call):
        print(f"Message {message.id} passing through...")
        return await next_call(message)

broker.add_middleware(LoggingMiddleware())
```

## 3. Custom Validation Rules

Enforce custom constraints on messages before they are processed.

### Validation Usage

```python
from agents_protocol.extensions import ValidationRule

class PriorityValidation(ValidationRule):
    async def validate(self, message):
        return message.priority >= MessagePriority.NORMAL
    
    def get_error_message(self):
        return "Priority too low"

broker.add_validation_rule(PriorityValidation())
```

## 4. Plugin Registries

### Channel Registry

Register and instantiate custom communication channels.

```python
from agents_protocol.channels import ChannelRegistry

ChannelRegistry.register("my_custom_transport", MyCustomChannel)
channel = ChannelRegistry.create("my_custom_transport", broker, host="...", port=...)
```

### Router Registry

Register custom routing logic.

```python
from agents_protocol.messaging import RouterRegistry

RouterRegistry.register("capability_router", CapabilityRouter)
broker.set_router(RouterRegistry.create("capability_router"))
```
