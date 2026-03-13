# Advanced Usage

Welcome to the advanced guide for `agents_protocol`! While `basic_usage.py` is enough to get you started with simple Request/Response patterns, this guide covers production-ready architectural patterns.

## 1. Direct Delivery vs. Broker Routing

By default, an `AgentMessage` should be routed via an intermediate `MessageBroker`.

```python
broker = MessageBroker()
agent1.connect(broker)

# This goes into the broker's queue, utilizing its internal MessageRouter logic:
await agent1.send_message(message)
```

However, if you know the physical endpoint of the agent (e.g. its HTTP address or WebSocket endpoint), you can bypass the broker queuing logic on the sender's side using the Channel directly:

```python
# Create a TCP Channel (listens on an ephemeral port assigned by the OS)
channel = TCPSocketChannel(broker, host="127.0.0.1", port=0)
await channel.start()

host, port = channel.get_address()

# Send directly to that TCP socket bypassing sender's internal broker queues completely
await channel.send(message, destination=f"{host}:{port}")
```

## 2. Advanced Routing Mechanisms

The `MessageRouter` component acts as the brains of the `MessageBroker`. You can inject your own routing logic via sub-classing or providing custom handlers:

```python
class CustomRouter(MessageRouter):
    def route_message(self, message: AgentMessage) -> list[str]:
        if message.priority == MessagePriority.CRITICAL:
            # Special broadcast logic for critical messages
            return self.get_all_active_agents()
            
        return super().route_message(message)

# Inject into a new broker
custom_broker = MessageBroker(router=CustomRouter())
```

## 3. Dynamic Port Allocation

If you are running multiple agents on the same host machine, it is highly recommended to NOT hardcode `port=8080`. Hardcoding ports leads to `Address already in use` collisions.

Instead, let the operating system dynamically assign ephemeral ports:

```python
ws_channel = WebSocketChannel(broker, port=0)
await ws_channel.start()
print("WebSocket listening on:", ws_channel.get_address())
```

## 4. Message Correlation

You can correlate entirely decoupled asynchronous request/response events using the `correlation_id` string on `AgentMessage`.

```python
# 1. Sender
req = AgentMessage(type=MessageType.REQUEST, content={"command": "build"})
print("Sent Tracking ID:", req.correlation_id)

# 2. Receiver
async def handle_request(msg: AgentMessage):
    reply = msg.create_reply({"status": "done"})
    # reply.correlation_id is already identical to req.correlation_id
    await self.send_message(reply)
```
