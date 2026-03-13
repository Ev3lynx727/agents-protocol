"""Agents Protocol - Standardized AI Agent Communication.

A Python library for standardized communication between AI agents using
a protocol-based system.
"""

from .version import __version__
from .protocol import (
    AgentMessage,
    AgentProtocol,
    MessageType,
    MessagePriority,
    MessageStatus,
)
from .agents import Agent, AgentRegistry
from .messaging import MessageBroker, MessageRouter
from .channels import (
    Channel,
    LocalChannel,
    HTTPChannel,
    WebSocketChannel,
    TCPSocketChannel,
)
from .persistence import MessageStore, InMemoryMessageStore
from .adapters import BaseAdapter, JSONRPCAdapter
from .bridge import BridgeAgent, StreamBridgeAgent
from .security import SecurityManager, AuthStatus, TLSHelper
from .cluster import ClusterManager, ClusterNodeInfo, ClusterPeer

__all__ = [
    "__version__",
    "AgentMessage",
    "AgentProtocol",
    "MessageType",
    "MessagePriority",
    "MessageStatus",
    "Agent",
    "AgentRegistry",
    "MessageBroker",
    "MessageRouter",
    "Channel",
    "LocalChannel",
    "HTTPChannel",
    "WebSocketChannel",
    "TCPSocketChannel",
    "MessageStore",
    "InMemoryMessageStore",
    "BaseAdapter",
    "JSONRPCAdapter",
    "BridgeAgent",
    "StreamBridgeAgent",
    "SecurityManager",
    "AuthStatus",
    "TLSHelper",
    "ClusterManager",
    "ClusterNodeInfo",
    "ClusterPeer",
]
