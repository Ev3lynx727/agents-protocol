"""Tests for HTTP connection pooling in HTTPChannel."""

import asyncio
import pytest
import httpx
from agents_protocol import MessageBroker, HTTPChannel, Agent, AgentMessage, MessageType


@pytest.mark.asyncio
async def test_http_pooling_initialization():
    """Test that HTTPChannel stores the client with pooling limits."""
    broker = MessageBroker()
    custom_limits = httpx.Limits(max_connections=50, max_keepalive_connections=10)
    channel = HTTPChannel(broker, host="127.0.0.1", port=0, pool_limits=custom_limits)

    await channel.start()

    try:
        assert channel._session is not None
        assert channel.pool_limits == custom_limits
    finally:
        await channel.stop()


@pytest.mark.asyncio
async def test_http_pooling_default_limits():
    """Test that HTTPChannel initializes default pooling limits."""
    broker = MessageBroker()
    channel = HTTPChannel(broker, host="127.0.0.1", port=0)

    await channel.start()

    try:
        assert channel._session is not None
        assert channel.pool_limits is not None
        assert channel.pool_limits.max_connections == 100
    finally:
        await channel.stop()
