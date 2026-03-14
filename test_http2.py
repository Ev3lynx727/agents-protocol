import asyncio

async def test():
    req = b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nHe"
    reader = asyncio.StreamReader()
    reader.feed_data(req)

    request_data = await reader.readuntil(b"\r\n\r\n")
    headers, body = request_data.split(b"\r\n\r\n", 1)
    print(f"headers: {headers}, body: {body}")

    content_length = 5
    reader.feed_data(b"llo")
    reader.feed_eof()

    print(f"remaining to read: {content_length - len(body)}")
    body += await reader.readexactly(content_length - len(body))
    print(f"final body: {body}")

asyncio.run(test())
