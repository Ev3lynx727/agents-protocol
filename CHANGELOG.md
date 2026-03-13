# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **3.6 Extension Points**:
  - Agent lifecycle hooks (`PRE/POST_CONNECT`, `PRE/POST_DISCONNECT`, `PRE/POST_MESSAGE_PROCESS`)
  - `MessageBroker` middleware support for intercepting and transforming messages
  - Custom `ValidationRule` system for enforcing message constraints
  - `ChannelRegistry` and `RouterRegistry` for pluggable transports and routing logic
- **3.5 Resilience Patterns**:
  - `RetryPolicy` with exponential backoff and jitter
  - `CircuitBreaker` for preventing cascading failures
  - Support for `TimeoutManager` across all channel types
  - Real-time metrics tracking for the `MessageBroker` (delivered, failed, etc.)
- **Clustering & Distribution**:
  - `ClusterManager` for peer-to-peer node coordination
  - Automatic peer discovery and heartbeats
  - Distributed message routing across cluster nodes
- **Security & Privacy**:
  - `SecurityManager` for token-based authentication
  - AES-GCM encryption for message content
  - Access Control Lists (ACL) for granular message authorization
- **Persistence**:
  - SQLite-based message store with history querying
  - Dead Letter Queue (DLQ) for failed message isolation
  - Message replay functionality from the DLQ
- **Performance**:
  - Optimized priority queue for high-throughput messaging (~275,000 msg/s)
  - Connection pooling for `HTTPChannel`
- **Documentation**:
  - Comprehensive feature guides for Security, Persistence, Resilience, Clustering, and Extensions
  - Major overhaul of `README.md` with architecture and usage details
- GitHub Actions CI/CD pipeline for automated testing and linting
- Test coverage reporting via `pytest-cov`
- `CONTRIBUTING.md`, advanced usage guide, and troubleshooting documentation
- `pre-commit` hooks for strictly enforcing `black`, `flake8`, and `mypy`
- Updated project requirements to Python 3.11

## [0.1.0] - Initial Release

### Added

- Core protocol enums (`MessageType`, `MessagePriority`, `MessageStatus`)
- Pydantic V2 strictly-typed model for `AgentMessage`
- `Agent` and `AgentRegistry` classes
- `MessageBroker` and `MessageRouter` for async message processing
- `LocalChannel` for in-memory processing
- `HTTPChannel` leveraging standard async REST
- `WebSocketChannel` for persistent bidirectional streaming
- `TCPSocketChannel` for extremely low-latency length-prefixed binary transport
- Automatic OS ephemeral port assignment logic for network channels (defaults to port `0`)
- Secure network bind isolation mapping `127.0.0.1`
