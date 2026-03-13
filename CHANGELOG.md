# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitHub Actions CI/CD pipeline for automated testing and linting
- Test coverage reporting via `pytest-cov`
- `CONTRIBUTING.md`, advanced usage guide, and troubleshooting documentation
- `pre-commit` hooks for strictly enforcing `black`, `flake8`, and `mypy`

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
