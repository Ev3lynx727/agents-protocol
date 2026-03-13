"""Tests for resilience patterns."""

import asyncio
import pytest
from agents_protocol.resilience import (
    RetryPolicy,
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)


@pytest.mark.asyncio
async def test_retry_policy_success():
    """Test that RetryPolicy succeeds if the operation succeeds eventually."""
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Transient error")
        return "Success"

    policy = RetryPolicy(max_retries=3, base_delay=0.1)
    result = await policy.execute(operation)

    assert result == "Success"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_policy_failure():
    """Test that RetryPolicy raises the last exception after max retries."""
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError(f"Permanent error {attempts}")

    policy = RetryPolicy(max_retries=2, base_delay=0.1)
    with pytest.raises(ValueError, match="Permanent error 3"):
        await policy.execute(operation)

    assert attempts == 3


@pytest.mark.asyncio
async def test_circuit_breaker_tripping():
    """Test that CircuitBreaker trips after enough failures."""
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.5, name="test")

    attempts = 0

    async def failing_op():
        nonlocal attempts
        attempts += 1
        raise ValueError("Fail")

    # Fail 3 times
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(failing_op)

    assert breaker.state == CircuitState.OPEN

    # 4th call should fail-fast with CircuitBreakerError
    with pytest.raises(CircuitBreakerError):
        await breaker.call(failing_op)

    assert attempts == 3  # Failing op not called when OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_recovery():
    """Test that CircuitBreaker recovers after timeout."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.2, name="test")

    async def failing_op():
        raise ValueError("Fail")

    async def success_op():
        return "Success"

    # Trip it
    with pytest.raises(ValueError):
        await breaker.call(failing_op)
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.3)

    # Next call should be HALF_OPEN then CLOSED
    result = await breaker.call(success_op)
    assert result == "Success"
    assert breaker.state == CircuitState.CLOSED
