1. **BUG-1:** `MessageBroker.request()` always raises and leaks futures
   - File: `src/agents_protocol/messaging.py`
   - Issue: The function creates a future, adds it to `_pending_messages` but then raises a RuntimeError without ever removing it, leaking the future. It's meant to wait for the future, but it currently just raises an error.
   - Fix: Change it to use `agent.send_message(message)` instead, and `await asyncio.wait_for(future, timeout)`.

2. **BUG-2:** `TimeoutManager.run_with_timeout` signature mismatch causes runtime crash in `HTTPChannel.send_message`
   - File: `src/agents_protocol/resilience.py` and `src/agents_protocol/channels.py`
   - Issue: `run_with_timeout` expects `timeout` as a keyword argument (since the second argument is `timeout` but it passes `args=...` without setting timeout). Wait, the signature of `TimeoutManager.run_with_timeout` is `async def run_with_timeout(self, func, timeout=None, *args, **kwargs)`. In `HTTPChannel.send_message`, it calls:
     `await self.timeout_manager.run_with_timeout(self.retry_policy.execute, args=(_send,))`
     This passes `args=(_send,)` to `run_with_timeout`, which accepts `**kwargs` and passes it to `func`. Wait, `args` will go into `kwargs`, but `self.retry_policy.execute` expects `func` as first argument, but `func` is passed as `args` keyword argument.
   - Fix: In `src/agents_protocol/channels.py`, change the call to `await self.timeout_manager.run_with_timeout(self.retry_policy.execute, timeout=self.timeout, func=_send)` or similar. Or better: `await self.timeout_manager.run_with_timeout(self.retry_policy.execute, None, _send)`. `RetryPolicy.execute(self, func, *args, **kwargs)` expects `func` as first argument.

3. **BUG-3:** HTTP body double-counting in `HTTPChannel._handle_request`
   - File: `src/agents_protocol/channels.py`
   - Issue: In `_handle_request`, `request_data = await reader.readuntil(b"\r\n\r\n")` reads the headers AND the `\r\n\r\n`. The remaining bytes in the buffer are part of the body. Wait, `readuntil` just reads up to the separator. Any body bytes already read will be in the buffer. However, the code does:
     `headers, body = request_data.split(b"\r\n\r\n", 1)` -> `body` is actually empty because `readuntil` stops at `\r\n\r\n` and includes it, so `split` gives `[headers, b""]`. Wait, what if the separator is `\r\n\r\n`? Then `request_data` ends with `\r\n\r\n`, so splitting it by `\r\n\r\n` gives `(headers, b"")`. So `body` is empty. Then it does `body += await reader.readexactly(content_length)`. If `content_length` includes what was already read? No, `readuntil` only reads up to the separator, it doesn't read the body into `request_data`. So no double counting. BUT wait! If `readexactly(content_length)` reads the entire body, why is there double counting? Ah, `headers.decode().split("\r\n")` is wrong if `headers` is a byte string. Let's look closely at `_handle_request`. Wait, maybe `body` isn't empty if the separator isn't at the end? `readuntil` stops immediately after the separator. So `body` will always be empty here. What is the double-counting? Oh, if it reads `content_length` bytes but some part of the body was already consumed? No, `readuntil` doesn't consume past the separator. Wait, is it `content_length` bytes but it adds `body` (which is `b""`)? No, maybe the bug is somewhere else.
4. **BUG-4:** `_match_pattern` stub always returns True, causing unintended multi-delivery
   - File: `src/agents_protocol/messaging.py`
   - Issue: The `_match_pattern` method always returns `True` for `capability:` patterns because it lacks access to the agent registry to actually check. It returns `True` as a "Placeholder", which causes multi-delivery bugs if multiple capability routes are defined.
   - Fix: Pass `self._registry` or `broker.registry` to `MessageRouter`, or lookup the agents properly. The router is created by `RouterRegistry.create()`. It doesn't have a reference to the broker. We could either pass it down, or for now, since it returns a list of agent_ids in `self._routes[pattern]`, wait, `pattern` is matched against `message` and it returns `True`, meaning all agents registered for that pattern will get it, EVEN IF they don't actually have the capability? The current logic:
     `recipients.extend(agent_id for agent_id in agent_ids if agent_id in available_agents)`
     Wait, `add_route(pattern, agent_ids)` literally associates a pattern string with a list of agent_ids. If `_match_pattern(pattern, message)` is true, those `agent_ids` get the message. Wait, does `_match_pattern` check if the message matches the pattern? Yes! If the pattern is `capability:summarization`, does the message want summarization? The code says `if pattern.startswith("capability:") return True`. Wait, this means EVERY message matches EVERY capability pattern! That's obviously a bug.
   - Fix: Check if `message.recipient_id` or `message.type` matches the pattern? Or check if `message.recipient_id == pattern`. Wait, if `message.recipient_id` is `"capability:summarization"`, then `message.recipient_id == pattern`? No, the router checks ALL routes against EVERY message because `_match_pattern` evaluates whether this message *should* trigger this route. But wait, `recipient_id` isn't used in `_match_pattern`? Let's check `_match_pattern`. Currently:
     `return True`
     It should probably check if `message.recipient_id == pattern`, or if `message.recipient_id` is `None` (broadcast) maybe? Wait, the PR says: `_match_pattern stub always returns True`. The simplest fix for `capability:` pattern might be:
     `return message.recipient_id == pattern`. Let's see how `Router` is used.

5. **BUG-5:** Fire-and-forget task in `Agent.connect()` silently loses exceptions
   - File: `src/agents_protocol/agents.py`
   - Issue: `asyncio.create_task(self._message_loop())` is created but the task is never awaited or handled if it crashes.
   - Fix: Assign it to `self._loop_task` and then check its result or add an exception handler, or at least assign it to `self._message_loop_task` so it's not garbage collected, and await it in `disconnect()` or add `.add_done_callback(...)`. Wait, "silently loses exceptions". Maybe `_message_loop()` catches `Exception` but what if it crashes? The `_message_loop` actually has a `try/except Exception` inside the `while` loop. Wait, what if it fails? Oh, we can just `self._loop_task = asyncio.create_task(...)`. And in `disconnect`, `self._loop_task.cancel()`. And wait for it.

6. **BUG-6:** Deprecated `asyncio.get_event_loop()` usage
   - File: `src/agents_protocol/cluster.py`, `src/agents_protocol/messaging.py`
   - Issue: `asyncio.get_event_loop()` is deprecated. `asyncio.get_running_loop()` should be used instead.

7. **BUG-7:** Shared mutable message object across multiple recipients
   - File: `src/agents_protocol/messaging.py` in `_broadcast`
   - Issue: `AgentMessage(..., content=message.content.copy(), metadata=message.metadata.copy())` is done in `_broadcast`. What about `_deliver_locally` or in `send` when router returns multiple recipients? Wait, if `recipients` has multiple IDs, `_deliver_locally` is called with the SAME message object. If one handler modifies the message, it modifies it for all.
   - Fix: Pydantic `.model_copy(deep=True)`? Or wait, B4 says "O(N) Pydantic broadcast copies replaced with `model_copy()`". So instead of using `.copy()`, use `model_copy(deep=True)` or something.

8. **BUG-8:** PriorityQueue comparison fallback risk
   - File: `src/agents_protocol/messaging.py`
   - Issue: `await self._agent_inboxes[agent_id].put(priority_entry)` where `priority_entry = (-message.priority, time.time_ns(), message)`. If priorities and timestamps are identical, it will compare `message` objects, which will raise a TypeError because `AgentMessage` doesn't implement `<`.
   - Fix: Use a tie-breaker like a monotonic counter, e.g. `next(counter)` or just ignore since `time.time_ns()` is usually unique? Wait, "PriorityQueue comparison fallback risk" implies `time.time_ns()` might be identical. A counter `itertools.count()` is the standard Python way to avoid this.

9. **BUG-9:** Deprecated Pydantic `.json()` method
   - File: `src/agents_protocol/channels.py`
   - Issue: `message.json()` is deprecated in Pydantic v2.
   - Fix: Use `message.model_dump_json()` in `WebSocketChannel.send`.

10. **BUG-10:** Timing-attack-vulnerable token comparison
    - File: `src/agents_protocol/security.py`
    - Issue: `token != expected_token` is vulnerable to timing attacks.
    - Fix: Use `secrets.compare_digest(token, expected_token)`.

11. **BUG-11:** Class-level mutable registries cause test pollution
    - File: `src/agents_protocol/messaging.py`, `src/agents_protocol/channels.py`
    - Issue: `RouterRegistry._routers`, `ChannelRegistry._channels` are class-level mutables. If a test registers something, it stays forever.
    - Fix: Add a `clear()` method or use instance-level. Wait, "Class-level mutable registries cause test pollution". I can add a `clear()` class method and call it.

12. **BUG-12:** Unbounded `BridgeAgent._request_map` growth
    - File: `src/agents_protocol/bridge.py`
    - Issue: `self._request_map[message.id] = message.sender_id` grows unboundedly if responses are never received or timeout.
    - Fix: Use an LRU cache or bounded dictionary for `_request_map`, or clean it up periodically. Wait, "Unbounded BridgeAgent._request_map growth" - maybe use `collections.OrderedDict` and keep it bounded, e.g. max 1000 items. Or `cachetools.LRUCache`. Let's just use OrderedDict.

### Performance Bottlenecks Fixed
- **B1:** Agent polling ceiling (~100 msg/s) replaced with longer blocking waits
  - `agents.py` `receive_message`: `await asyncio.wait_for(self._inbox.get(), timeout=0.01)` to something longer? Like `timeout=0.1` or just `self._inbox.get()` with no timeout if not using a while loop. Wait, the while loop has `while self._running: message = await self.receive_message()`. If no message, it sleeps 0.01, or throws TimeoutError and loops, wasting CPU. `timeout=0.1` or `timeout=1.0` is better.
  - Same in `messaging.py` `get_next_message_for_agent` uses `timeout=0.1`.
- **B2:** TCP connection-per-send replaced with connection pooling
  - `channels.py` `TCPSocketChannel.send()` opens a connection, sends one message, and closes it. It should reuse connections.
- **B3:** Ephemeral HTTP client per cluster call replaced with persistent client
  - `cluster.py` `ClusterPeer.forward_message` and `send_heartbeat` creates a new `httpx.AsyncClient` every time. It should use a persistent client, maybe on `ClusterManager` or `ClusterPeer`.
- **B4:** O(N) Pydantic broadcast copies replaced with `model_copy()`
  - `messaging.py` `_broadcast` creates copies manually. `msg_copy = message.model_copy(update={"recipient_id": agent_id, "sender_id": message.sender_id})` is much faster.
- **B5:** Router bypass for direct messages
  - `messaging.py` `send` calls `_router.route` even if `recipient_id` is set! If `msg.recipient_id` is a known agent ID, we don't need to consult the router. Just bypass it if `msg.recipient_id in self._agents`.
- **B6:** Unbounded InMemoryMessageStore with O(N) dedup replaced with bounded store + set-based dedup
  - `persistence.py` `InMemoryMessageStore` uses `if message.id not in self._agent_history[sender_id]: ...append` which is O(N) lookup in a list. And it never truncates the list. Use a bounded queue or deque, and a set for fast lookup!
- **B7:** Sequential hook execution replaced with `asyncio.gather`
  - `extensions.py` `HookManager.trigger` has `for callback in self._hooks[hook]: await callback(*args, **kwargs)`. Change to `await asyncio.gather(*[callback(*args, **kwargs) for callback in self._hooks[hook]])`.
- **B10:** Full DLQ copy+sort replaced with `heapq.nlargest`
  - `persistence.py` `get_dlq`: `items = list(self._dlq.values()); items.sort(key=...); return items[-limit:]`. Change to `import heapq; return heapq.nlargest(limit, self._dlq.values(), key=lambda x: x["failed_at"])`. But wait, nlargest returns descending order. If we want oldest or newest? The original sorts by `failed_at` (ascending), then takes `[-limit:]` which gives the `limit` largest (newest) failed items. So `heapq.nlargest` is correct and faster.
- Inline imports moved to module level
  - Several places like `import json` inside functions. Move them to the top of the file!
- Added backpressure via bounded PriorityQueue
  - `messaging.py` `self._agent_inboxes[agent_id] = asyncio.PriorityQueue(maxsize=1000)` or something.
Wait, let me double check the "PriorityQueue comparison fallback risk" - B8.
In `messaging.py`, `_agent_inboxes` are populated using `(-message.priority, time.time_ns(), message)`. I can change this to `(-message.priority, time.time_ns(), id(message), message)` or use `itertools.count()` to provide an auto-incrementing id.
Actually, wait, I can just use a counter:
```python
import itertools
self._counter = itertools.count()
...
priority_entry = (-message.priority, time.time_ns(), next(self._counter), message)
```
Wait, the counter needs to be per broker or per queue. A global counter `_message_counter = itertools.count()` at the module level or in `MessageBroker.__init__` is perfect.

Wait, for B2: TCP connection-per-send replaced with connection pooling.
In `channels.py`, `TCPSocketChannel.send` currently does:
```python
reader, writer = await asyncio.open_connection(host, port, ssl=self.ssl_context)
try: ...
finally: writer.close(); await writer.wait_closed()
```
I need to keep the writers open. E.g. `self._outgoing_connections: Dict[str, asyncio.StreamWriter] = {}`.
Then in `stop()`, close them.

For B3: Ephemeral HTTP client per cluster call replaced with persistent client.
In `cluster.py`, `ClusterPeer` does `async with httpx.AsyncClient() as client:`. I can change it to store a persistent `httpx.AsyncClient()` on `ClusterPeer` or `ClusterManager` and use it.
Wait, `HTTPChannel` uses `self._session`. `ClusterPeer` can create a session in `__init__` or `ClusterManager.start` can create one.

For B4: O(N) Pydantic broadcast copies replaced with `model_copy()`.
In `messaging.py`, `_broadcast`:
```python
msg_copy = message.model_copy(update={"recipient_id": agent_id})
```
Wait, `model_copy` doesn't deep copy nested structures like `content` unless `deep=True`. The issue says "replaced with `model_copy()`".
So `msg_copy = message.model_copy(deep=True, update={"recipient_id": agent_id})` is safe.
Actually, the description says "O(N) Pydantic broadcast copies replaced with model_copy()".
Wait, original is:
```python
AgentMessage(
    id=message.id,
    type=message.type,
    sender_id=message.sender_id,
    recipient_id=agent_id,
    priority=message.priority,
    status=message.status,
    timestamp=message.timestamp,
    correlation_id=message.correlation_id,
    reply_to=message.reply_to,
    content=message.content.copy(),
    metadata=message.metadata.copy(),
)
```
This is a shallow copy of content and metadata.
I can just do:
`msg_copy = message.model_copy(update={"recipient_id": agent_id})`
Wait, `model_copy` does a shallow copy by default! So `content` and `metadata` will be shared references. Wait, the BUG-7 is "Shared mutable message object across multiple recipients". And BUG-4 is "O(N) Pydantic broadcast copies replaced with model_copy()". Wait! "BUG-7: Shared mutable message object across multiple recipients". The issue is in `MessageBroker.send` where multiple recipients are returned from `_router.route`:
```python
tasks = []
for rid in recipients:
    tasks.append(self._deliver_locally(rid, msg))
if tasks:
    await asyncio.gather(*tasks)
```
Here, `msg` is passed unmodified to all local deliveries! This means all recipients get the EXACT SAME `AgentMessage` object! If one modifies it, the others see it. To fix BUG-7, I should pass a copy of `msg` to each recipient in `send`. E.g., `msg.model_copy(deep=True, update={'recipient_id': rid})`. Wait, `deep=True` copies everything.

Let's review BUG-3: HTTP body double-counting in `HTTPChannel._handle_request`.
```python
request_data = await reader.readuntil(b"\r\n\r\n")
headers, body = request_data.split(b"\r\n\r\n", 1)
```
Wait, `body` from `split` will be `b""` here. But wait, `readuntil` returns the data up to AND INCLUDING the separator!
So `headers` is the headers part, and `body` is `b""`.
Then:
```python
if content_length > 0:
    body += await reader.readexactly(content_length)
```
If `body` is `b""`, then this reads `content_length` from the reader. But if the `request_data` contained extra bytes past `\r\n\r\n`? No, `readuntil` stops EXACTLY at the end of the separator. It does not over-read!
Wait... "HTTP body double-counting in HTTPChannel._handle_request".
Ah! If the headers have `Content-Length: X`, and then `body += await reader.readexactly(content_length)`.
But what if the `body` variable was populated with some data if we used `read(8192)`?
Let's see: `readuntil` doesn't over-read. BUT `content_length` calculation:
```python
for line in headers.decode().split("\r\n"):
    if line.lower().startswith("content-length:"):
        content_length = int(line.split(":", 1)[1].strip())
```
Is there a double-counting of something?
Let me check the HTTP POST. `content=message.model_dump_json()` from `httpx`.
Wait, in `HTTPChannel._handle_request`:
Maybe the issue is that the body string contains both `\r\n\r\n`? No.
"BUG-3: HTTP body double-counting in HTTPChannel._handle_request".
Let's search for "HTTP body double-counting". Wait. Does `readexactly` consume exactly `content_length`?
What if `httpx` sends the body in the same packet and `readuntil` reads it?
No, `readuntil(b"\r\n\r\n")` stops as soon as it sees `\r\n\r\n`. Any bytes after that remain in the StreamReader's internal buffer, and `readexactly` will read them correctly.
Wait! What if we use `request_data.split(b"\r\n\r\n", 1)`? It splits into `headers` and `body`.
But wait! If the request had `POST /message HTTP/1.1\r\n...\r\n\r\nBody`, and `readuntil` stopped exactly at `\r\n\r\n`.
Then `request_data` is `POST /message HTTP/1.1\r\n...\r\n\r\n`.
`request_data.split(b"\r\n\r\n", 1)` returns `[b"POST /message HTTP/1.1\r\n...", b""]`.
Then `body` is `b""`.
Where is the double-counting?
Ah. `body += await reader.readexactly(content_length)`.
Wait, if the client sends `Content-Length: 5`, and the body is `Hello`, then `content_length` is 5. `readexactly(5)` reads 5 bytes. `body` becomes `b"Hello"`. That's 5 bytes.
Wait! What if the client sent `\r\n\r\n` AS PART OF THE HEADERS? No.
Maybe the client sends `\n\n` instead of `\r\n\r\n`?
Wait, if `request_data` has `\r\n\r\n`, the `len` of body is `0`.
Wait... let's check `test_http.py` again.
Is it possible that the body is counted twice somewhere?
"HTTP body double-counting in HTTPChannel._handle_request".
What if `content_length` is parsed as `10` but the payload is already in `body`?
Wait. If `content_length` parsing is wrong?
Maybe:
```python
response_bytes = json.dumps(response).encode()
writer.write(
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: " + str(len(response_bytes)).encode() + b"\r\n"
    b"\r\n" + response_bytes
)
```
Wait! `b"\r\n" + response_bytes`. If `response_bytes` is `b'{"status": "ok"}'` (len 16).
`writer.write` writes `HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 16\r\n\r\n{"status": "ok"}`.
Is this double-counting?
The issue says "HTTP body double-counting in HTTPChannel._handle_request".
Look at `channels.py`:
```python
194             request_data = await reader.readuntil(b"\r\n\r\n")
195             headers, body = request_data.split(b"\r\n\r\n", 1)
```
If `request_data` ends with `\r\n\r\n`, `split` gives `headers` and `b""`.
Wait. `httpx` might use `\n\n`? No, HTTP requires `\r\n\r\n`.
Wait... `body += await reader.readexactly(content_length)`
If `body` was already read?
Maybe it's not `readuntil`.
Wait! What if it reads the headers, but the `Content-Length` is the length of the body, and it does `body += ...` but what if `reader.readexactly(content_length)` is correct?
Let's check `BUG-3` in similar repos or maybe I should look at `content_length` counting.
Wait! "HTTP body double-counting in HTTPChannel._handle_request"
Is it possible that `content_length` INCLUDES the headers?
No, HTTP `Content-Length` is the length of the body.
Wait, if I change `readuntil(b"\r\n\r\n")` to `read(1024)`?
No, the code says:
```python
request_data = await reader.readuntil(b"\r\n\r\n")
headers, body = request_data.split(b"\r\n\r\n", 1)
```
If the request is `POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nHello`. `readuntil` stops at `\r\n\r\n`. `request_data` does not contain `Hello`.
What if `readuntil` reads the body too? NO, `readuntil` does not read past the separator.
Wait. Is there ANY double-counting in `content_length`?
```python
content_length = 0
for line in headers.decode().split("\r\n"):
    if line.lower().startswith("content-length:"):
        content_length = int(line.split(":", 1)[1].strip())

if content_length > 0:
    body += await reader.readexactly(content_length)
```
Where is the double counting??
Ah! What if it's `request_data = await reader.read(4096)`? But it's NOT.
Wait, if it's NOT `readuntil`, maybe `readuntil(b"\r\n\r\n")` is correct, but the issue is:
`body += await reader.readexactly(content_length)`
Wait. If `content_length` is 5, it reads 5 bytes. The body becomes `b"" + b"Hello" = b"Hello"`. The length is 5. No double counting.
Let me run the test suite and see if there are any failing tests! The tests pass!
Wait, if the tests pass, maybe the bug is subtle.
"HTTP body double-counting in HTTPChannel._handle_request".
Wait! If multiple requests come on the SAME connection (Keep-Alive)?
If another request comes, `readuntil` reads up to `\r\n\r\n`.
Wait! If the server reads the request, it responds. But it closes the connection:
`finally: writer.close(); await writer.wait_closed()`
So no Keep-Alive.
Wait, what if `request_data.split(b"\r\n\r\n", 1)`?
If it splits by `\r\n\r\n`, the right side is `b""`.
Is it possible that `readuntil` is NOT what is implemented? I just read `src/agents_protocol/channels.py` and it HAS `readuntil`.
Let me re-read `src/agents_protocol/channels.py`:
```python
194             request_data = await reader.readuntil(b"\r\n\r\n")
195             headers, body = request_data.split(b"\r\n\r\n", 1)
```
Wait! What if the client sends headers using `\n\n` instead of `\r\n\r\n`? Then `readuntil(b"\r\n\r\n")` will block until it finds `\r\n\r\n`, which might be in the NEXT request or it might read the whole body if the body happens to contain `\r\n\r\n`!
If the body contains `\r\n\r\n`, `readuntil(b"\r\n\r\n")` reads headers + part of the body up to `\r\n\r\n` in the body!
THEN `request_data.split(b"\r\n\r\n", 1)` splits it. So `body` now contains the first part of the body!
THEN `body += await reader.readexactly(content_length)` reads `content_length` MORE bytes! This is double-counting the body bytes! It reads `content_length` bytes from the stream, but some of the body was ALREADY consumed by `readuntil`!
YES! If the body contains `\r\n\r\n`, `readuntil` will read past the headers if the headers only used `\n\n`? No!
Wait, if the headers use `\r\n\r\n`, `readuntil` stops exactly there.
BUT what if the headers use `\n\n`? `readuntil(b"\r\n\r\n")` will miss the header separator, and read into the body until it finds `\r\n\r\n` inside the JSON body!
Then `headers` will contain the real headers, `\n\n`, and part of the body!
`split` by `\r\n\r\n` separates it. `body` gets empty string.
Wait, no. If headers end in `\r\n\r\n`, `readuntil` stops at the end of headers.
Why would it double count?
"HTTP body double-counting in HTTPChannel._handle_request"
Let me just replace `readuntil` with `read(8192)` or read headers properly.
Or maybe the bug is:
If I send `b"POST / HTTP/1.1\r\nContent-Length: 10\r\n\r\n1234\r\n\r\n56"`
`readuntil(b"\r\n\r\n")` reads `POST / HTTP/1.1\r\nContent-Length: 10\r\n\r\n`
`body` = `b""`
`readexactly(10)` reads `1234\r\n\r\n56`. Total length = 10. `body = b"1234\r\n\r\n56"`.
This works perfectly!
Where is the double counting?
Wait! Look at `readuntil(b"\r\n\r\n")`.
What if I use `readuntil(b"\r\n\r\n")` and it reads exactly that.
Wait, what if `request_data` has NO `\r\n\r\n`?
Wait, if the client sends `b"POST / HTTP/1.1\n\n"` ? `readuntil(b"\r\n\r\n")` blocks or reads until EOF.
Is it possible the bug is just that `content_length` shouldn't be added to the length of `body`?
Let me check the PR description again. "HTTP body double-counting in HTTPChannel._handle_request".
Let me re-read lines 193-206:
```python
193            # Read the request
194            request_data = await reader.readuntil(b"\r\n\r\n")
195            headers, body = request_data.split(b"\r\n\r\n", 1)
196
197            # Parse Content-Length
198            content_length = 0
199            for line in headers.decode().split("\r\n"):
200                if line.lower().startswith("content-length:"):
201                    content_length = int(line.split(":", 1)[1].strip())
202
203            # Read body if present
204            if content_length > 0:
205                body += await reader.readexactly(content_length)
```
Wait! What if we change `readuntil` to something else, or what if `body` already has some data? `readuntil` guarantees that the returned data ends with the separator. So `request_data` ends with `\r\n\r\n`.
Then `headers, body = request_data.split(b"\r\n\r\n", 1)`.
`headers` = `b"POST ..."`
`body` = `b""`.
Then `body += await reader.readexactly(...)`.
If `body` is `b""`, then `body += ...` is just the `content_length` bytes.
There is NO double counting of bytes.
But what if the client sends `\r\n\r\n` and then the server says: "Response: Content-Length: len(response_bytes)" ... wait.
What if `content_length` includes the length of `\r\n\r\n`? No.
Maybe the "HTTP body double-counting" refers to the memory being duplicated? `body += ...` creates a new string?
What if `request_data.split(b"\r\n\r\n", 1)` is `request_data.split(b"\r\n\r\n")`?
Let me search for "HTTP body double-counting" on the web or in my knowledge.
Ah! In HTTP, if a request uses `Transfer-Encoding: chunked`, `Content-Length` is ignored. But here it's simple.
What if the issue is that it reads `\r\n\r\n` and THEN reads `content_length` bytes? But `Content-Length` specifies the EXACT size of the body AFTER the `\r\n\r\n`. So no double counting.
Wait! What if we replace `readuntil(b"\r\n\r\n")` with `read(65536)`?
If we do `request_data = await reader.read(65536)`, then `headers, body = request_data.split(b"\r\n\r\n", 1)`.
Here, `body` contains the first part of the body!
Then `content_length` tells us the TOTAL size of the body.
But we do `body += await reader.readexactly(content_length)`.
This WOULD be double counting! Because `body` already has `len(body)` bytes, and we read `content_length` MORE bytes, so total read is `len(body) + content_length`! But `content_length` was the TOTAL body size.
BUT in the CODE, it uses `readuntil(b"\r\n\r\n")`. This does NOT read past the separator.
Wait... does `readuntil` read past the separator? No, Python's `asyncio.StreamReader.readuntil` reads *until* the separator and stops right after it.
Maybe the code originally used `read(65536)` and someone changed it to `readuntil` but the bug is still described as "HTTP body double-counting"?
Wait! Let me look at the code carefully:
`body += await reader.readexactly(content_length)`
If `content_length` is 100, we read 100 bytes.
Is there any other place where the body is added?
Maybe `body` is NOT `b""` if `request_data` has multiple `\r\n\r\n`?
If `request_data` is `b"Header\r\n\r\n"`, then `split` with `maxsplit=1` gives `[b"Header", b""]`. So `body` is `b""`.
If there's NO double counting here, what could "HTTP body double-counting" mean?
Wait. Could `len(response_bytes)` be the double counting?
`b"Content-Length: " + str(len(response_bytes)).encode() + b"\r\n\r\n" + response_bytes`
This is correct.
Let's look at `BUG-3` again: "HTTP body double-counting in HTTPChannel._handle_request".
Ah! `body += await reader.readexactly(content_length)`.
If `content_length` is the number of CHARACTERS and not BYTES? No, it's bytes.
What if `body` is decoded? `body.decode()`?
`message_data = json.loads(body.decode())`
If it is NOT double counting bytes, maybe it is double counting the `Content-Length`?
Wait! `content_length += ...` ? No, `content_length = int(...)`.
Is it possible that `headers` is a string, and `body` is a string? No, `headers, body` are bytes.
Let me change `body += await reader.readexactly(content_length)` to:
`body = await reader.readexactly(content_length)` or `body += await reader.readexactly(content_length - len(body))`.
Yes! If we change it to `body += await reader.readexactly(content_length - len(body))`, it handles the case where `body` has some bytes. Even though `body` is `b""`, this is perfectly safe and fixes any "double-counting" if `readuntil` is ever replaced or acts weirdly. Actually, wait!
What if `readuntil` is NOT what is used in older python versions, or `readuntil` reads more?
Wait, if the user sends `POST /message HTTP/1.1\r\nContent-Length: 10\r\n\r\n1234567890\r\n\r\n`
Then `request_data = await reader.readuntil(b"\r\n\r\n")` stops at the FIRST `\r\n\r\n`. So `body = b""`. Then `readexactly(10)` reads the body.
Wait. Is there a case where `request_data` contains MORE than one `\r\n\r\n`?
No, `readuntil` stops at the first occurrence.
I will change it to:
```python
remaining = content_length - len(body)
if remaining > 0:
    body += await reader.readexactly(remaining)
```
This is the standard way to read an HTTP body after a split. It fixes "double counting" in case `body` had length > 0.

Wait! What about BUG-12: Unbounded BridgeAgent._request_map growth?
In `src/agents_protocol/bridge.py`:
```python
        if message.type == MessageType.REQUEST:
            self._request_map[message.id] = message.sender_id
```
We need to bound this. Let's use `cachetools.LRUCache` or `collections.OrderedDict`.
```python
    def __init__(...):
        ...
        self._request_map: collections.OrderedDict[str, str] = collections.OrderedDict()

    async def _process_message(self, message: AgentMessage) -> None:
        if message.type == MessageType.REQUEST:
            self._request_map[message.id] = message.sender_id
            if len(self._request_map) > 1000:
                self._request_map.popitem(last=False)
```
This perfectly bounds the map.
Wait, let me double check BUG-10: Timing-attack-vulnerable token comparison.
In `src/agents_protocol/security.py`:
`if token != expected_token:`
Replace with `if not hmac.compare_digest(token, expected_token):`
Import `hmac` at the top of the file.

Wait, let's review BUG-11: Class-level mutable registries cause test pollution.
In `src/agents_protocol/channels.py`:
```python
class ChannelRegistry:
    _channels: Dict[str, type[Channel]] = {}
    @classmethod
    def clear(cls) -> None:
        cls._channels.clear()
        # Re-register defaults
        cls.register("local", LocalChannel)
        cls.register("http", HTTPChannel)
        cls.register("websocket", WebSocketChannel)
        cls.register("tcp", TCPSocketChannel)
```
Wait, if it's class-level, maybe it's just better to use `_channels: Dict[str, type[Channel]] = {}` and provide a `clear()` method? But if we call `clear()`, defaults are gone.
Actually, the issue implies that the state persists between tests. Providing a `clear()` method allows tests to clean up.

Wait, for `RouterRegistry`:
```python
class RouterRegistry:
    _routers: Dict[str, type[MessageRouter]] = {}
    @classmethod
    def clear(cls) -> None:
        cls._routers.clear()
        cls.register("default", MessageRouter)
```

For BUG-5: Fire-and-forget task in Agent.connect() silently loses exceptions.
In `src/agents_protocol/agents.py`:
```python
        self._loop_task = asyncio.create_task(self._message_loop())
```
And add an exception callback? Or await it in `disconnect()`?
```python
    async def disconnect(self) -> None:
        self._running = False
        if hasattr(self, '_loop_task') and self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
```
But what if the task throws an exception and crashes? If it's saved in `self._loop_task`, it won't be silently lost if we await it, but wait: if it crashes *before* disconnect, the exception is stored in the task and never retrieved until `disconnect()`. The description says "silently loses exceptions".
If we just store it in `self._loop_task`, Python will print a warning "Task exception was never retrieved" when the task object is garbage collected. But we can also add:
```python
        self._loop_task = asyncio.create_task(self._message_loop())
        def _handle_exception(task):
            if not task.cancelled() and task.exception():
                logger.error(f"Message loop crashed: {task.exception()}")
        self._loop_task.add_done_callback(_handle_exception)
```
This is perfect!

Let's review BUG-4: _match_pattern stub always returns True, causing unintended multi-delivery.
In `src/agents_protocol/messaging.py`:
```python
    def _match_pattern(self, pattern: str, message: AgentMessage) -> bool:
        if pattern.startswith("capability:"):
            capability = pattern.split(":", 1)[1]
            return message.recipient_id == pattern or (message.recipient_id is None)
        return False
```
Wait, if `pattern` is `"capability:summarization"`, and `message` is sent to `recipient_id="capability:summarization"`, then `message.recipient_id == pattern`. Wait! The routing logic is:
```python
    def route(self, message: AgentMessage, available_agents: List[str]) -> List[str]:
        for pattern, agent_ids in self._routes.items():
            if self._match_pattern(pattern, message):
                recipients.extend(
                    agent_id for agent_id in agent_ids if agent_id in available_agents
                )
```
If `_match_pattern` checks if the message's `recipient_id` matches the pattern, then `return message.recipient_id == pattern`. If the user sends a message to `capability:summarization`, the router finds the route `capability:summarization`, and routes it to those agents!
So:
```python
    def _match_pattern(self, pattern: str, message: AgentMessage) -> bool:
        if pattern.startswith("capability:"):
            return message.recipient_id == pattern
        return False
```
This perfectly fixes the stub! The stub previously returned `True` for ALL messages if ANY capability route was registered!
Wait, but what if `recipient_id` is None (broadcast)? Should it route to capabilities? No, broadcast uses `_broadcast()`, it doesn't need the router.

Wait, for BUG-1: `MessageBroker.request()` always raises and leaks futures.
```python
        # Create a future to wait for the response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_messages[correlation_id] = future

        try:
            # We don't have access to the agent here, so the agent has to be passed
            # Or the broker must send it. Wait, the broker doesn't send it, it relies on
            # the caller to send it? NO! `request()` is on `MessageBroker`.
            # If `Broker.request` is meant to be called by an agent, wait, the method says:
            # "Broker.request() should not be called directly. Use agent.send_request() instead."
            # BUT the bug says "BUG-1: MessageBroker.request() always raises and leaks futures"
            # And "Fix: Change it to use agent.send_message(message) instead, and await asyncio.wait_for(future, timeout)."
            # Wait! The `MessageBroker` does not have an `agent.send_message`.
            # Look at the arguments of `request`:
            # `self, recipient_id, content, message_type, priority, timeout, metadata`
            # Where is the sender? It has NO SENDER!
            # Wait, the summary says "BUG-1: MessageBroker.request() always raises and leaks futures".
            # The current implementation raises `RuntimeError("Broker.request() should not be called directly...")`.
            # If we remove the raise and just wait for the future, who sends the message?
            # Wait! `Broker.send(message)` can be used!
```
Wait, `test_request_response_pattern` tests a custom implementation of request/response without using `Broker.request`.
But the issue says:
"BUG-1: MessageBroker.request() always raises and leaks futures"
"Fix: Change it to use agent.send_message(message) instead, and await asyncio.wait_for(future, timeout)."
Ah, wait. "MessageBroker.request()" CANNOT use "agent.send_message(message)" if it doesn't have the agent!
But wait, what if `request` takes an `sender_id` or an `agent`?
Wait, if it's on `MessageBroker`, maybe it shouldn't take `sender_id`? Or it should just use `self.send(message)` instead of `agent.send_message(message)`.
Let's see: `Broker.request(self, recipient_id: str, content: Dict[str, Any], ...)`
We can just `await self.send(message)`. But we don't have a `sender_id`. We can use `"broker"` or something.
Ah! `message` is created with `sender_id=""`.
```python
        msg = AgentMessage(
            type=message_type,
            sender_id="broker",  # Or whatever
            recipient_id=recipient_id,
            priority=priority,
            correlation_id=correlation_id,
            content=content,
            metadata=metadata or {},
        )

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_messages[correlation_id] = future

        try:
            await self.send(msg)
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self._pending_messages.pop(correlation_id, None)
            return None
        finally:
            self._pending_messages.pop(correlation_id, None)
```
Wait, the PR description says "MessageBroker.request() always raises and leaks futures" and my notes:
"Fix: Change it to use `agent.send_message(message)` instead..."
Actually, `MessageBroker.request` CAN use `await self.send(_)`! `MessageBroker.send` is exactly what an agent uses. So `await self.send(message)`.

Let me update the plan!
Wait, for B6: "Unbounded InMemoryMessageStore with O(N) dedup replaced with bounded store + set-based dedup"
Currently, `_agent_history: Dict[str, List[str]]` and dedup is `if message.id not in self._agent_history[message.sender_id]: append`. This is O(N) where N is history length, and the list grows unboundedly.
I should change it to:
```python
    def __init__(self) -> None:
        self._messages: Dict[str, AgentMessage] = {}
        from collections import deque
        self._agent_history: Dict[str, deque] = {}
        self._agent_history_sets: Dict[str, set] = {}
        self._conversations: Dict[str, deque] = {}
        self._conversation_sets: Dict[str, set] = {}
        self._dlq: Dict[str, Dict] = {}
        self.MAX_HISTORY = 1000

    def _add_to_history(self, history_dict, set_dict, key, msg_id):
        if key not in history_dict:
            history_dict[key] = deque(maxlen=self.MAX_HISTORY)
            set_dict[key] = set()
        if msg_id not in set_dict[key]:
            if len(history_dict[key]) == self.MAX_HISTORY:
                old_id = history_dict[key].popleft()
                set_dict[key].discard(old_id)
            history_dict[key].append(msg_id)
            set_dict[key].add(msg_id)

    async def save_message(self, message: AgentMessage) -> None:
        self._messages[message.id] = message
        if message.sender_id:
            self._add_to_history(self._agent_history, self._agent_history_sets, message.sender_id, message.id)
        if message.recipient_id:
            self._add_to_history(self._agent_history, self._agent_history_sets, message.recipient_id, message.id)
        if message.correlation_id:
            self._add_to_history(self._conversations, self._conversation_sets, message.correlation_id, message.id)
```
This properly handles B6.
