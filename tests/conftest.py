"""Pytest configuration for agents_protocol tests."""

import asyncio
import pytest

# Set the default event loop policy for Windows
if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

pytest_plugins = ['pytest_asyncio']