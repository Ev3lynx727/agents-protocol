# Resilience Patterns

Ensure reliable communication even in unstable environments using built-in resilience patterns.

## 1. Retry Policies

Automatically retry failed network operations with exponential backoff and jitter.

### Retry Configuration

```python
from agents_protocol.resilience import RetryPolicy

# Configure 5 retries with 1s base delay
retry_policy = RetryPolicy(max_retries=5, base_delay=1.0)

# Used internally by HTTPChannel and ClusterPeer
```

## 2. Circuit Breakers

Prevent cascading failures by "tripping" when a remote service is consistently failing.

### States

- **CLOSED**: Normal operation.
- **OPEN**: Fail-fast when threshold exceeded.
- **HALF_OPEN**: Periodically probe if remote service has recovered.

### CB Configuration

```python
from agents_protocol.resilience import CircuitBreaker

# Trip after 5 failures, wait 60s to recover
cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
```

## 3. Metrics Tracking

Monitor the health of your agent system through broker metrics.

### Usage

```python
metrics = broker.metrics
print(f"Delivered: {metrics['delivered']}")
print(f"Failed: {metrics['failed']}")
print(f"Security Denied: {metrics['security_denied']}")
print(f"Validation Failed: {metrics['validation_failed']}")
```

## 4. Timeouts

Ensure operations don't hang indefinitely.

### Timeout Configuration

```python
from agents_protocol.resilience import TimeoutManager

timeout_manager = TimeoutManager(default_timeout=30.0)
# All channels support custom timeout intervals
```
