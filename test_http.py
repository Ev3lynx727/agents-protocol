import asyncio

async def test():
    req = b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nHello"
    reader = asyncio.StreamReader()
    reader.feed_data(req)
    reader.feed_eof()

    request_data = await reader.readuntil(b"\r\n\r\n")
    headers, body = request_data.split(b"\r\n\r\n", 1)
    print(f"headers: {headers}, body: {body}")

    body += await reader.readexactly(5)
    print(f"final body: {body}")

asyncio.run(test())
