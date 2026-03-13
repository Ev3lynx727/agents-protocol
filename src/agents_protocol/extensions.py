"""Extension points and hook definitions for agents_protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Awaitable, Tuple

if TYPE_CHECKING:
    from .protocol import AgentMessage


class AgentHook(Enum):
    """Lifecycle hooks for agents."""

    PRE_CONNECT = auto()
    POST_CONNECT = auto()
    PRE_DISCONNECT = auto()
    POST_DISCONNECT = auto()
    PRE_MESSAGE_PROCESS = auto()
    POST_MESSAGE_PROCESS = auto()


class BaseMiddleware(ABC):
    """Base class for message processing middleware.

    Middleware can intercept and transform messages before they are processed
    by the broker or the agent.
    """

    @abstractmethod
    async def __call__(
        self, message: AgentMessage, next_call: Callable[[AgentMessage], Awaitable[Any]]
    ) -> Any:
        """Process a message.

        Args:
            message: The message to process
            next_call: The next middleware or the final handler in the chain

        Returns:
            The result of the next_call
        """
        pass


class ValidationRule(ABC):
    """Base class for custom message validation rules."""

    @abstractmethod
    async def validate(self, message: AgentMessage) -> bool:
        """Validate a message.

        Args:
            message: The message to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def get_error_message(self) -> str:
        """Get the error message if validation fails."""
        pass


class HookManager:
    """Manages lifecycle hooks for agents."""

    def __init__(self) -> None:
        self._hooks: Dict[AgentHook, List[Callable[..., Awaitable[None]]]] = {
            hook: [] for hook in AgentHook
        }

    def register(
        self, hook: AgentHook, callback: Callable[..., Awaitable[None]]
    ) -> None:
        """Register a callback for a hook."""
        self._hooks[hook].append(callback)

    async def trigger(self, hook: AgentHook, *args: Any, **kwargs: Any) -> None:
        """Trigger all callbacks for a hook."""
        for callback in self._hooks[hook]:
            await callback(*args, **kwargs)


class ExtensionManager:
    """Registry for middleware, hooks, and plugins."""

    def __init__(self) -> None:
        self._middleware: List[BaseMiddleware] = []
        self._validation_rules: List[ValidationRule] = []

    def add_middleware(self, middleware: BaseMiddleware) -> None:
        """Add middleware to the processing chain."""
        self._middleware.append(middleware)

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        self._validation_rules.append(rule)

    async def validate_message(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Validate a message against all registered rules."""
        for rule in self._validation_rules:
            if not await rule.validate(message):
                return False, rule.get_error_message()
        return True, None

    async def process_with_middleware(
        self, message: AgentMessage, handler: Callable[[AgentMessage], Awaitable[Any]]
    ) -> Any:
        """Execute middleware chain around a handler."""

        async def _execute_chain(index: int, msg: AgentMessage) -> Any:
            if index < len(self._middleware):
                return await self._middleware[index](
                    msg, lambda m: _execute_chain(index + 1, m)
                )
            return await handler(msg)

        return await _execute_chain(0, message)
