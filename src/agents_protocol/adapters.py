"""Protocol adapters for translating between different agent communication standards."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .protocol import AgentMessage, MessageType


class BaseAdapter(ABC):
    """Abstract base class for protocol adapters."""

    @abstractmethod
    def to_protocol(self, external_message: Any) -> AgentMessage:
        """Translate an external message format to AgentMessage."""
        pass

    @abstractmethod
    def from_protocol(self, internal_message: AgentMessage) -> Any:
        """Translate an AgentMessage to an external format."""
        pass


class JSONRPCAdapter(BaseAdapter):
    """Adapter for JSON-RPC 2.0 (compatible with ACP and MCP)."""

    def to_protocol(self, external_message: Dict[str, Any] | str) -> AgentMessage:
        """Translate JSON-RPC request/notification to AgentMessage."""
        if isinstance(external_message, str):
            data = json.loads(external_message)
        else:
            data = external_message

        # Basic JSON-RPC validation
        if data.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC version. Expected '2.0'")

        method = data.get("method")
        params = data.get("params", {})
        msg_id = data.get("id")
        result = data.get("result")
        error = data.get("error")

        # Map JSON-RPC to AgentMessage
        if result is not None or error is not None:
            msg_type = MessageType.RESPONSE
            content = result if result is not None else error
        elif method is not None:
            msg_type = MessageType.REQUEST if msg_id is not None else MessageType.NOTIFICATION
            content = {"method": method, "params": params}
        else:
            msg_type = MessageType.NOTIFICATION
            content = data

        return AgentMessage(
            type=msg_type,
            sender_id="external",  # To be set by bridge agent
            content=content,
            correlation_id=str(msg_id) if msg_id is not None else None,
        )

    def from_protocol(self, internal_message: AgentMessage) -> Dict[str, Any]:
        """Translate AgentMessage (RESPONSE/NOTIFICATION/REQUEST) to JSON-RPC."""
        # Detect if we are sending a response or a notification
        if internal_message.type == MessageType.RESPONSE:
            return {
                "jsonrpc": "2.0",
                "id": internal_message.correlation_id,
                "result": internal_message.content
            }
        elif internal_message.type == MessageType.REQUEST:
            return {
                "jsonrpc": "2.0",
                "method": internal_message.content.get("method", "call"),
                "params": internal_message.content.get("params", {}),
                "id": internal_message.id
            }
        else:
            # For notifications or other types, treat as JSON-RPC notification
            return {
                "jsonrpc": "2.0",
                "method": internal_message.content.get("method", "notify") if isinstance(internal_message.content, dict) else "notify",
                "params": internal_message.content.get("params", internal_message.content) if isinstance(internal_message.content, dict) else internal_message.content
            }
