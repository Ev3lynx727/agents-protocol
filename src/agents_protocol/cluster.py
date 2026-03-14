"""Clustering and peer-to-peer logic for distributed brokers."""

from __future__ import annotations
import httpx
import uuid

import asyncio
import logging
from typing import Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

from .resilience import CircuitBreaker, RetryPolicy, CircuitBreakerError

if TYPE_CHECKING:
    from .messaging import MessageBroker
    from .protocol import AgentMessage

logger = logging.getLogger(__name__)


class ClusterNodeInfo(BaseModel):
    """Information about a node in the broker cluster."""

    node_id: str
    endpoint: str  # e.g., "http://127.0.0.1:8080"
    capabilities: List[str] = Field(default_factory=list)
    last_seen: float = Field(default_factory=lambda: asyncio.get_running_loop().time())


class ClusterPeer:
    """Represents a connection to a peer broker in the cluster."""

    def __init__(
        self,
        node_info: ClusterNodeInfo,
        broker: MessageBroker,
        client: httpx.AsyncClient,
    ):
        self.node_info = node_info
        self.broker = broker
        self.client = client
        self._connected = False
        self.circuit_breaker = CircuitBreaker(
            name=f"peer-{node_info.node_id}", failure_threshold=3, recovery_timeout=60.0
        )
        self.retry_policy = RetryPolicy(max_retries=2, base_delay=0.5, jitter=True)

    async def forward_message(self, message: AgentMessage) -> bool:
        """Forward a message to this peer node with resilience."""

        async def _forward() -> bool:

            # In a real scenario, this would use a persistent session
            # or a dedicated protocol
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    f"{self.node_info.endpoint}/internal/forward",
                    content=message.model_dump_json(),
                )
                response.raise_for_status()  # Trigger retry if not 2xx
                return response.status_code == 200

        try:
            from typing import cast

            # Wrap in both circuit breaker and retry policy
            return cast(
                bool,
                await self.circuit_breaker.call(self.retry_policy.execute, _forward),
            )
        except CircuitBreakerError:
            logger.debug(
                f"Circuit OPEN for peer {self.node_info.node_id}. Skipping forward."
            )
            return False
        except Exception as e:
            logger.debug(
                f"Failed to forward message to peer {self.node_info.node_id} "
                f"after retries: {e}"
            )
            return False

    async def send_heartbeat(self) -> bool:
        """Send a heartbeat to this peer."""
        try:

            async with httpx.AsyncClient(timeout=1.0) as client:
                response = await client.get(f"{self.node_info.endpoint}/health")
                if response.status_code == 200:
                    self.node_info.last_seen = asyncio.get_running_loop().time()
                    return True
                return False
        except Exception:
            return False


class ClusterManager:
    """Manages the cluster state and peer connections."""

    def __init__(
        self,
        broker: MessageBroker,
        node_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        self.broker = broker
        self.node_id = node_id or str(uuid.uuid4())
        self.endpoint = endpoint
        self.peers: Dict[str, ClusterPeer] = {}
        self.remote_agents: Dict[str, str] = {}  # agent_id -> node_id
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        """Start the cluster manager and heartbeat loop."""
        if self._running:
            return
        self._client = httpx.AsyncClient(timeout=2.0)
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Cluster manager started for node {self.node_id}")

    async def stop(self) -> None:
        """Stop the cluster manager."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.aclose()
        logger.info(f"Cluster manager stopped for node {self.node_id}")

    async def _heartbeat_loop(self) -> None:
        """Periodically check peer health."""
        while self._running:
            try:
                tasks = [peer.send_heartbeat() for peer in self.peers.values()]
                if tasks:
                    await asyncio.gather(*tasks)

                # Cleanup old peers (e.g., not seen for 30 seconds)
                now = asyncio.get_running_loop().time()
                to_remove = [
                    node_id
                    for node_id, peer in self.peers.items()
                    if now - peer.node_info.last_seen > 30.0
                ]
                for node_id in to_remove:
                    logger.warning(f"Peer node {node_id} timed out and was removed.")
                    del self.peers[node_id]
                    # Also cleanup remote agents associated with this node
                    agents_to_remove = [
                        a_id
                        for a_id, n_id in self.remote_agents.items()
                        if n_id == node_id
                    ]
                    for a_id in agents_to_remove:
                        del self.remote_agents[a_id]

            except Exception as e:
                logger.error(f"Error in cluster heartbeat loop: {e}")

            await asyncio.sleep(10.0)

    def add_peer(self, node_info: ClusterNodeInfo) -> None:
        """Add a peer to the cluster."""
        if node_info.node_id == self.node_id:
            return
        if not self._client:
            self._client = httpx.AsyncClient(timeout=2.0)
        self.peers[node_info.node_id] = ClusterPeer(
            node_info, self.broker, self._client
        )
        logger.info(f"Added peer node {node_info.node_id} at {node_info.endpoint}")

    def register_remote_agent(self, agent_id: str, node_id: str) -> None:
        """Register an agent located on a remote node."""
        self.remote_agents[agent_id] = node_id
        logger.debug(f"Registered remote agent {agent_id} on node {node_id}")

    def get_peer_for_agent(self, agent_id: str) -> Optional[ClusterPeer]:
        """Get the peer node that hosts the given agent."""
        node_id = self.remote_agents.get(agent_id)
        if node_id:
            return self.peers.get(node_id)
        return None

    async def broadcast_to_peers(self, message: AgentMessage) -> None:
        """Broadcast a message to all peers in the cluster."""
        tasks = [peer.forward_message(message) for peer in self.peers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
