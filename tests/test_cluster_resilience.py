"""Integration tests for resilience in clustering."""

import asyncio
import pytest
from agents_protocol import (
    MessageBroker,
    AgentMessage,
    MessageType,
    ClusterManager,
    ClusterNodeInfo,
)
from agents_protocol.resilience import CircuitState


@pytest.mark.asyncio
async def test_cluster_forwarding_resilience():
    """Test that message forwarding failure trips the circuit breaker and updates metrics."""
    broker = MessageBroker()
    manager = ClusterManager(broker, node_id="node1")
    broker._cluster_manager = manager

    # Mock a peer that is "down" (unreachable endpoint)
    peer_info = ClusterNodeInfo(node_id="node2", endpoint="http://invalid.local:9999")
    manager.add_peer(peer_info)
    manager.register_remote_agent("remote_agent", "node2")
    peer = manager.peers["node2"]

    # Configure breaker for fast testing
    peer.circuit_breaker.failure_threshold = 2
    peer.retry_policy.max_retries = 1
    peer.retry_policy.base_delay = 0.01

    msg = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="local_agent",
        recipient_id="remote_agent",
        content={"data": "test"},
    )

    # Attempt forwarding - should fail and retry
    from agents_protocol.protocol import MessageStatus

    status = await broker.send(msg)

    assert status == MessageStatus.FAILED
    assert broker.metrics["failed"] == 1

    # First failure recorded in breaker
    assert peer.circuit_breaker._failure_count == 1
    assert peer.circuit_breaker.state == CircuitState.CLOSED

    # Second attempt to trip breaker
    await broker.send(msg)
    assert peer.circuit_breaker.state == CircuitState.OPEN
    assert broker.metrics["failed"] == 2

    # Third attempt should fail-fast via circuit breaker
    # Metrics should still increment as 'failed'
    await broker.send(msg)
    assert broker.metrics["failed"] == 3
    # peer.circuit_breaker._failure_count shouldn't increase when OPEN
    assert peer.circuit_breaker._failure_count == 2
