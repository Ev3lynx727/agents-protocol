"""Security components for agent authentication, authorization, and encryption."""

from __future__ import annotations

import ssl
import logging
from typing import Dict, Optional, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class AuthStatus(Enum):
    """Status of an authentication attempt."""

    SUCCESS = "success"
    UNAUTHORIZED = "unauthorized"
    EXPIRED = "expired"
    INVALID_SIGNATURE = "invalid_signature"


class SecurityManager:
    """Manages agent identity, authentication, and access control.

    In internal scenarios, this can be used to verify pre-shared keys (PSK)
    or JWT tokens passed in message headers.
    """

    def __init__(self, secret_key: Optional[str] = None):
        """Initialize the security manager.

        Args:
            secret_key: Root secret used for HMAC signatures or token verification.
        """
        self._secret_key = secret_key
        self._allowed_agents: Dict[str, List[str]] = (
            {}
        )  # agent_id -> list of allowed recipient_ids (ACL)
        self._agent_keys: Dict[str, str] = {}  # agent_id -> psk

    def register_agent_credentials(self, agent_id: str, psk: str) -> None:
        """Register a pre-shared key for a specific agent."""
        self._agent_keys[agent_id] = psk

    def set_acl(self, agent_id: str, allowed_recipients: List[str]) -> None:
        """Set an Access Control List for an agent."""
        self._allowed_agents[agent_id] = allowed_recipients

    def verify_message(self, message: Any) -> AuthStatus:
        """Verify the authenticity and authorization of a message.

        This checks the 'security' field of the AgentMessage.
        """
        security_context = getattr(message, "security", {}) or {}

        token = security_context.get("token")
        sender_id = getattr(message, "sender_id", None)
        recipient_id = getattr(message, "recipient_id", None)

        # 1. Verification of identity (if keys are registered)
        if sender_id in self._agent_keys:
            expected_token = self._agent_keys[sender_id]
            if token != expected_token:
                logger.warning(f"Unauthorized message from agent {sender_id}")
                return AuthStatus.UNAUTHORIZED

        # 2. Authorization (ACL check)
        if sender_id in self._allowed_agents:
            allowed = self._allowed_agents[sender_id]
            if recipient_id not in allowed and "*" not in allowed:
                logger.warning(
                    f"Agent {sender_id} not authorized to message {recipient_id}"
                )
                return AuthStatus.UNAUTHORIZED

        return AuthStatus.SUCCESS


class TLSHelper:
    """Utility for creating SSL/TLS contexts for channels."""

    @staticmethod
    def create_server_context(
        certfile: str, keyfile: str, ca_file: Optional[str] = None
    ) -> ssl.SSLContext:
        """Create a secure SSL context for a server (e.g. TCPSocketChannel)."""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        if ca_file:
            context.load_verify_locations(cafile=ca_file)
            context.verify_mode = ssl.CERT_REQUIRED
        return context

    @staticmethod
    def create_client_context(
        ca_file: Optional[str] = None,
        certfile: Optional[str] = None,
        keyfile: Optional[str] = None,
    ) -> ssl.SSLContext:
        """Create a secure SSL context for a client."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if ca_file:
            context.load_verify_locations(cafile=ca_file)
        if certfile and keyfile:
            context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        return context
