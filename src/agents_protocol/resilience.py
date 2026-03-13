"""Resilience patterns for robust agent communication."""

import asyncio
import random
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional, Type, List

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(Exception):
    """Exception raised when the circuit breaker is open."""

    pass


class RetryPolicy:
    """Policy for retrying failed operations with exponential backoff and jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[List[Type[Exception]]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or [Exception]

    async def execute(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with retries."""
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Check if we should retry on this exception
                if not any(isinstance(e, ex_type) for ex_type in self.retry_on):
                    raise e

                last_exception = e
                if attempt == self.max_retries:
                    break

                # Calculate delay
                delay = min(
                    self.max_delay, self.base_delay * (self.exponential_base**attempt)
                )
                if self.jitter:
                    delay = delay * (0.5 + random.random())

                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)

        raise last_exception


class CircuitBreaker:
    """Circuit breaker pattern to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default",
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0

    def _on_success(self):
        """Called when a call succeeds."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' RESOLVED. Closing circuit.")
            self.state = CircuitState.CLOSED
        self._failure_count = 0

    def _on_failure(self):
        """Called when a call fails."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if (
            self.state == CircuitState.CLOSED
            and self._failure_count >= self.failure_threshold
        ):
            logger.warning(f"Circuit breaker '{self.name}' TRIPPED. Opening circuit.")
            self.state = CircuitState.OPEN
        elif self.state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}' failed during recovery. Re-opening."
            )
            self.state = CircuitState.OPEN

    def record_success(self):
        """Public method to record a successful call."""
        self._on_success()

    def record_failure(self):
        """Public method to record a failed call."""
        self._on_failure()

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Call the function through the circuit breaker."""
        # Check if we should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                logger.info(
                    f"Circuit breaker '{self.name}' attempting recovery (HALF_OPEN)."
                )
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e


class TimeoutManager:
    """Helper to manage timeouts for async operations."""

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout

    async def run_with_timeout(
        self, func: Callable[..., Any], timeout: Optional[float] = None, *args, **kwargs
    ) -> Any:
        """Run an async function with a timeout."""
        t = timeout if timeout is not None else self.default_timeout
        try:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=t)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Operation timed out after {t}s")
