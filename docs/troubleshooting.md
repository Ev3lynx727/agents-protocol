# Troubleshooting

Here are some common issues you may encounter when setting up or distributing your agents using `agents_protocol`.

## 1. WinError 1214: The format of the specified network name is invalid

**Symptom:** You are running `agents_protocol` natively on Windows, and `asyncio.open_connection()` crashes when trying to test or send a TCP/HTTP payload default locally.

**Cause:** This happens largely due to an upstream issue in Python's Windows async event loop when resolving the binding wildcard address `0.0.0.0` over connection streams.

**Fix:** Ensure your Channels are bound to `127.0.0.1` natively instead:
```python
channel = HTTPChannel(broker, host="127.0.0.1")
```
*(By default, all Channels since v0.1.0 are natively protected from this.)*

## 2. OSError: [Errno 98] Address already in use

**Symptom:** You get an "address already in use" exception when `channel.start()` is called.

**Cause:** You are hardcoding `port=8080` (or another port) and running multiple agents (or running agents simultaneously) that clash trying to bind to the same listener port on the host operating system.

**Fix:** Set `port=0`. The operating system will automatically provide an extremely robust, completely unpredictable free ephemeral port natively.
```python
tcp_channel = TCPSocketChannel(broker, port=0)
await tcp_channel.start()
host, port = tcp_channel.get_address()
print(f"I am bound perfectly to: {host}:{port}")
```

## 3. Agents are dropping messages silently

**Symptom:** `channel.send(message, destination)` returns `MessageStatus.FAILED` or messages just don't appear in the `MessageBroker` handlers of the receiver.

**Cause:** You may have forgotten to call `await agent.connect(broker)`. Before an agent can be queued messages, the agent has to be locally registered with its respective receiving broker.

## 4. Pytest Warnings `ResourceWarning: unclosed event loop`

**Symptom:** You see resource leaks indicating unclosed TCP sockets or background task streams after a test finishes.

**Cause:** Your test tearDown sequence isn't correct. Ensure you are universally awaiting the shutdown instructions cleanly:
```python
try:
    await channel.start()
finally:
    await channel.stop() # Automatically triggers `server.wait_closed()`
```
