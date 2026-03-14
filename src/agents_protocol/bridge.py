"""Bridge agents for connecting external systems to the agents_protocol."""

from __future__ import annotations

import asyncio
import logging
import json
import collections
from typing import Any, Dict, Optional, TYPE_CHECKING
from .agents import Agent
from .protocol import AgentMessage, MessageType
from .adapters import BaseAdapter, JSONRPCAdapter

if TYPE_CHECKING:
    from .messaging import MessageBroker

logger = logging.getLogger(__name__)


class BridgeAgent(Agent):
    """Base class for agents that bridge external systems to the protocol."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        adapter: Optional[BaseAdapter] = None,
        capabilities: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(agent_id, name, capabilities, metadata)
        self.adapter = adapter or JSONRPCAdapter()
        self._request_map: collections.OrderedDict[str, str] = (
            collections.OrderedDict()
        )  # msg_id -> sender_id

    async def _process_message(self, message: AgentMessage) -> None:
        """Forward internal messages to the external system."""
        if message.type == MessageType.REQUEST:
            self._request_map[message.id] = message.sender_id
            if len(self._request_map) > 1000:
                self._request_map.popitem(last=False)

        try:
            external_msg = self.adapter.from_protocol(message)
            await self.send_to_external(external_msg)
        except Exception as e:
            logger.error(f"Bridge {self.agent_id} failed to forward to external: {e}")

    async def send_to_external(self, message: Any) -> None:
        """Abstract method to send data to the bridged external system."""
        raise NotImplementedError("Bridge agents must implement send_to_external")

    async def handle_external_message(self, data: Any) -> None:
        """Called when a message is received from the external system."""
        try:
            internal_msg = self.adapter.to_protocol(data)
            internal_msg.sender_id = self.agent_id

            # Try to route response back to original requester
            if (
                internal_msg.type == MessageType.RESPONSE
                and internal_msg.correlation_id
            ):
                recipient = self._request_map.pop(internal_msg.correlation_id, None)
                if recipient:
                    internal_msg.recipient_id = recipient

            await self.send_message(internal_msg)
        except Exception as e:
            logger.error(
                f"Bridge {self.agent_id} failed to process external message: {e}"
            )


class StreamBridgeAgent(BridgeAgent):
    """Bridges an asynchronous stream (reader/writer pair) to the protocol."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        adapter: Optional[BaseAdapter] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_id, name, adapter, **kwargs)
        self.reader = reader
        self.writer = writer
        self._external_loop_task: Optional[asyncio.Task] = None

    async def connect(self, broker: MessageBroker) -> None:
        """Connect and start the external message listener."""
        await super().connect(broker)
        self._external_loop_task = asyncio.create_task(self._external_message_loop())

    async def disconnect(self) -> None:
        """Stop loops and close the stream."""
        if self._external_loop_task:
            self._external_loop_task.cancel()
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:
            pass
        await super().disconnect()

    async def send_to_external(self, message: Any) -> None:
        """Serialize and write to the stream with newline delimiter."""
        data = json.dumps(message) + "\n"
        self.writer.write(data.encode())
        await self.writer.drain()

    async def _external_message_loop(self) -> None:
        """Listen for newline-delimited JSON messages from the stream."""
        while self._running:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                data = json.loads(line.decode())
                await self.handle_external_message(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in external loop for {self.agent_id}: {e}")
                await asyncio.sleep(0.1)
