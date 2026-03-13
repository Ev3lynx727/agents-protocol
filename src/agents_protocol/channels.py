"""Communication channels for agent messaging."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple, cast
import asyncio
import struct
import logging
from .protocol import AgentMessage, MessageStatus
from .messaging import MessageBroker

logger = logging.getLogger(__name__)


class Channel(ABC):
    """Abstract base class for communication channels.

    Channels provide the transport layer for agent communication.
    They can be local (in-process), HTTP-based, WebSocket-based, etc.
    """

    def __init__(self, broker: MessageBroker):
        """Initialize the channel.

        Args:
            broker: The message broker to use for routing
        """
        self.broker = broker
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """Start the channel and begin listening for messages."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""

    @abstractmethod
    async def send(self, message: AgentMessage, destination: str) -> MessageStatus:
        """Send a message through this channel.

        Args:
            message: The message to send
            destination: The destination agent ID or channel address

        Returns:
            The status of the sent message
        """

    async def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running

    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get host and port this channel is bound to, if applicable."""
        return None


class LocalChannel(Channel):
    """In-process channel for agents in the same Python process.

    This is the simplest and fastest channel for local agent communication.
    It directly uses the broker's message routing without network overhead.
    """

    def __init__(self, broker: MessageBroker):
        """Initialize the local channel."""
        super().__init__(broker)

    async def start(self) -> None:
        """Start the local channel."""
        self._running = True
        logger.info("Local channel started")

    async def stop(self) -> None:
        """Stop the local channel."""
        self._running = False
        logger.info("Local channel stopped")

    async def send(self, message: AgentMessage, destination: str) -> MessageStatus:
        """Send a message directly through the broker.

        Args:
            message: The message to send
            destination: The recipient agent ID

        Returns:
            The status of the sent message
        """
        if not self._running:
            raise RuntimeError("Local channel is not running")

        message.status = MessageStatus.SENT
        await self.broker.send(message)
        return message.status


class HTTPChannel(Channel):
    """HTTP-based channel for agent communication over HTTP.

    This channel uses HTTP/REST for communication between agents
    running on different machines or processes.
    """

    def __init__(
        self,
        broker: MessageBroker,
        host: str = "127.0.0.1",
        port: int = 0,
        agent_id: Optional[str] = None,
    ):
        """Initialize the HTTP channel.

        Args:
            broker: The message broker to use
            host: Host to bind the HTTP server to
            port: Port to bind the HTTP server to
            agent_id: Optional agent ID for this endpoint
        """
        super().__init__(broker)
        self.host = host
        self.port = port
        self.agent_id = agent_id
        self._server: Optional[asyncio.Server] = None
        self._session: Optional[Any] = None  # httpx.AsyncClient

    async def start(self) -> None:
        """Start the HTTP server."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for HTTPChannel. Install with: pip install httpx"
            )

        self._session = httpx.AsyncClient()
        self._server = await asyncio.start_server(
            self._handle_request, self.host, self.port
        )

        # Update host/port with the actual bound address (useful if port=0)
        addr = self._server.sockets[0].getsockname()
        self.host, self.port = cast(Tuple[str, int], addr[:2])

        self._running = True
        logger.info(f"HTTP channel started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._session:
            await self._session.aclose()
        self._running = False
        logger.info("HTTP channel stopped")

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming HTTP request.

        Args:
            reader: Stream reader
            writer: Stream writer
        """
        try:
            # Read the request
            request_data = await reader.readuntil(b"\r\n\r\n")
            headers, body = request_data.split(b"\r\n\r\n", 1)

            # Parse Content-Length
            content_length = 0
            for line in headers.decode().split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())

            # Read body if present
            if content_length > 0:
                body += await reader.readexactly(content_length)

            # Parse the request
            request_line = headers.decode().split("\r\n")[0]
            method, path, _ = request_line.split(" ")

            if method == "POST" and path == "/message":
                # Handle incoming message
                import json

                message_data = json.loads(body.decode())
                message = AgentMessage(**message_data)

                # Deliver to broker
                await self.broker.send(message)

                # Send response
                response = {"status": "ok", "message_id": message.id}
                response_bytes = json.dumps(response).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(response_bytes)).encode() + b"\r\n"
                    b"\r\n" + response_bytes
                )
            else:
                # 404 Not Found
                writer.write(b"HTTP/1.1 404 Not Found\r\n\r\n")

            await writer.drain()
        except Exception as e:
            logger.error(f"Error handling HTTP request: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def send(self, message: AgentMessage, destination: str) -> MessageStatus:
        """Send a message via HTTP to another agent.

        Args:
            message: The message to send
            destination: The HTTP URL of the recipient agent

        Returns:
            The status of the sent message
        """
        if not self._running or not self._session:
            raise RuntimeError("HTTP channel is not running")

        try:
            pass

            url = destination
            headers = {"Content-Type": "application/json"}
            response = await self._session.post(
                url, content=message.json(), headers=headers, timeout=30.0
            )
            response.raise_for_status()
            message.status = MessageStatus.DELIVERED
            return message.status
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            message.status = MessageStatus.FAILED
            return message.status

    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get the HTTP server's bound host and port."""
        if self._server and self._server.sockets:
            # cast to Tuple[str, int] for mypy
            addr = self._server.sockets[0].getsockname()
            return cast(Tuple[str, int], addr[:2])
        return None


class WebSocketChannel(Channel):
    """WebSocket-based channel for real-time bidirectional communication.

    This channel uses WebSockets for persistent connections between agents,
    enabling real-time message streaming.
    """

    def __init__(
        self,
        broker: MessageBroker,
        host: str = "127.0.0.1",
        port: int = 0,
        agent_id: Optional[str] = None,
    ):
        """Initialize the WebSocket channel.

        Args:
            broker: The message broker to use
            host: Host to bind the WebSocket server to
            port: Port to bind the WebSocket server to
            agent_id: Optional agent ID for this endpoint
        """
        super().__init__(broker)
        self.host = host
        self.port = port
        self.agent_id = agent_id
        self._server: Optional[Any] = None  # websockets.server.Serve
        self._connections: Dict[str, Any] = {}  # agent_id -> WebSocket connection

    async def start(self) -> None:
        """Start the WebSocket server."""
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "websockets is required for WebSocketChannel. "
                "Install with: pip install websockets"
            )

        self._server = await websockets.serve(
            self._handle_connection, self.host, self.port  # type: ignore[arg-type]
        )

        # Update host/port with actual bound address
        addr = self._server.sockets[0].getsockname()
        self.host, self.port = cast(Tuple[str, int], addr[:2])

        self._running = True
        logger.info(f"WebSocket channel started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server and close all connections."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Close all connections
        for ws in self._connections.values():
            await ws.close()

        self._connections.clear()
        self._running = False
        logger.info("WebSocket channel stopped")

    async def _handle_connection(self, websocket: Any, path: Any) -> None:
        """Handle an incoming WebSocket connection.

        Args:
            websocket: The WebSocket connection
            path: The connection path
        """
        agent_id = None
        try:
            # First message should be agent identification
            message = await websocket.recv()
            import json

            data = json.loads(message)

            if data.get("type") == "identify":
                agent_id = data.get("agent_id")
                self._connections[agent_id] = websocket
                logger.info(f"Agent {agent_id} connected via WebSocket")

                # Send acknowledgment
                await websocket.send(
                    json.dumps({"type": "connected", "agent_id": agent_id})
                )

                # Listen for messages
                async for message in websocket:
                    msg_data = json.loads(message)
                    agent_message = AgentMessage(**msg_data)
                    await self.broker.send(agent_message)
            else:
                logger.warning("Unknown message type during WebSocket handshake")
                await websocket.close()
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            if agent_id and agent_id in self._connections:
                del self._connections[agent_id]

    async def send(self, message: AgentMessage, destination: str) -> MessageStatus:
        """Send a message via WebSocket to another agent.

        Args:
            message: The message to send
            destination: The agent ID of the recipient (must be connected via WebSocket)

        Returns:
            The status of the sent message
        """
        if not self._running:
            raise RuntimeError("WebSocket channel is not running")

        if destination not in self._connections:
            logger.warning(f"Agent {destination} not connected via WebSocket")
            message.status = MessageStatus.FAILED
            return message.status

        try:
            pass

            ws = self._connections[destination]
            await ws.send(message.json())
            message.status = MessageStatus.DELIVERED
            return message.status
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            message.status = MessageStatus.FAILED
            return message.status

    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get the WebSocket server's bound host and port."""
        if self._server and self._server.sockets:
            # cast to Tuple[str, int] for mypy
            addr = self._server.sockets[0].getsockname()
            return cast(Tuple[str, int], addr[:2])
        return None


class TCPSocketChannel(Channel):
    """TCP Socket channel for high-performance agent communication.

    This channel uses raw TCP sockets via asyncio streams with length-prefixed
    message framing, providing low latency and high throughput for agent communication.
    """

    def __init__(
        self,
        broker: MessageBroker,
        host: str = "127.0.0.1",
        port: int = 0,
        agent_id: Optional[str] = None,
    ):
        """Initialize the TCP Socket channel.

        Args:
            broker: The message broker to use
            host: Host to bind the TCP server to
            port: Port to bind the TCP server to
            agent_id: Optional agent ID for this endpoint
        """
        super().__init__(broker)
        self.host = host
        self.port = port
        self.agent_id = agent_id
        self._server: Optional[asyncio.Server] = None
        self._connections: set[asyncio.Task] = set()

    async def start(self) -> None:
        """Start the TCP server."""
        self._server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )

        # Update host/port with actual bound address
        addr = self._server.sockets[0].getsockname()
        self.host, self.port = cast(Tuple[str, int], addr[:2])

        self._running = True
        logger.info(f"TCP Socket channel started on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the TCP server and close any active background handler tasks."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Cancel any active connection handler tasks
        for task in self._connections:
            if not task.done():
                task.cancel()

        if self._connections:
            await asyncio.gather(*self._connections, return_exceptions=True)
            self._connections.clear()

        self._running = False
        logger.info("TCP Socket channel stopped")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming TCP connection task wrapper to track tasks."""
        task = asyncio.current_task()
        if task:
            self._connections.add(task)

        try:
            await self._process_stream(reader, writer)
        except asyncio.CancelledError:
            pass
        finally:
            if task and task in self._connections:
                self._connections.remove(task)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_stream(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Process messages from the incoming stream until the connection closes."""
        peername = writer.get_extra_info("peername")
        logger.debug(f"TCP connection accepted from {peername}")

        try:
            while self._running:
                # Read 4-byte message length
                try:
                    raw_msglen = await reader.readexactly(4)
                except asyncio.IncompleteReadError:
                    # Connection closed by peer
                    break

                if not raw_msglen:
                    break

                msglen = struct.unpack(">I", raw_msglen)[0]

                # Protect against incredibly large messages (e.g. 10MB limit)
                if msglen > 10 * 1024 * 1024:
                    logger.warning(
                        f"Message from {peername} exceeds length limit: {msglen} bytes"
                    )
                    break

                # Read actual message payload
                try:
                    data = await reader.readexactly(msglen)
                except asyncio.IncompleteReadError:
                    break

                import json

                try:
                    msg_dict = json.loads(data.decode())
                    message = AgentMessage(**msg_dict)

                    # Deliver to our local broker
                    await self.broker.send(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON message from {peername}: {e}")
                except Exception as e:
                    logger.error(f"Error handling message from {peername}: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"TCP stream error with {peername}: {e}")

    async def send(self, message: AgentMessage, destination: str) -> MessageStatus:
        """Send a message via TCP to another agent.

        Args:
            message: The message to send
            destination: The target host and port format "host:port",
                e.g. "127.0.0.1:8082"

        Returns:
            The status of the sent message
        """
        if not self._running:
            raise RuntimeError("TCP Socket channel is not running")

        try:
            host, port_str = destination.split(":")
            port = int(port_str)

            # Windows asyncio.open_connection fails with WinError 1214 if
            # host is "0.0.0.0"
            if host == "0.0.0.0":
                host = "127.0.0.1"

        except ValueError:
            logger.error(
                f"Invalid TCP destination format: {destination}. Expected 'host:port'"
            )
            message.status = MessageStatus.FAILED
            return message.status

        try:
            # We open a temporary connection for sending.
            reader, writer = await asyncio.open_connection(host, port)

            try:
                data = message.json().encode()
                # Big-endian 4-byte unsigned integer indicating length
                msg_length = struct.pack(">I", len(data))

                writer.write(msg_length + data)
                await writer.drain()
                message.status = MessageStatus.DELIVERED
            finally:
                writer.close()
                await writer.wait_closed()

            return message.status
        except Exception as e:
            logger.error(f"TCP send to {destination} failed: {e}")
            message.status = MessageStatus.FAILED
            return message.status

    def get_address(self) -> Optional[Tuple[str, int]]:
        """Get the TCP server's bound host and port."""
        if self._server and self._server.sockets:
            # cast to Tuple[str, int] for mypy
            addr = self._server.sockets[0].getsockname()
            return cast(Tuple[str, int], addr[:2])
        return None
