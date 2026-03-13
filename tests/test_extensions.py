import asyncio
import pytest
from typing import Any, Callable, Awaitable
from agents_protocol.protocol import AgentMessage, MessageType, MessageStatus
from agents_protocol.agents import Agent
from agents_protocol.messaging import MessageBroker, MessageRouter
from agents_protocol.extensions import AgentHook, BaseMiddleware, ValidationRule


class MockMiddleware(BaseMiddleware):
    def __init__(self):
        self.called = False
        self.processed_message = None

    async def __call__(self, message: AgentMessage, next_call: Callable[[AgentMessage], Awaitable[Any]]) -> Any:
        self.called = True
        message.metadata["middleware_processed"] = True
        result = await next_call(message)
        self.processed_message = message
        return result


class MockValidationRule(ValidationRule):
    def __init__(self, succeed: bool = True):
        self.succeed = succeed
        self.called = False

    async def validate(self, message: AgentMessage) -> bool:
        self.called = True
        return self.succeed

    def get_error_message(self) -> str:
        return "Mock validation failed"


@pytest.mark.asyncio
async def test_agent_lifecycle_hooks():
    broker = MessageBroker()
    agent = Agent("test_agent", "Test Agent")
    
    hooks_triggered = []
    
    async def hook_callback(a, *args):
        hooks_triggered.append(True)
        
    agent.register_hook(AgentHook.PRE_CONNECT, hook_callback)
    agent.register_hook(AgentHook.POST_CONNECT, hook_callback)
    
    await agent.connect(broker)
    assert len(hooks_triggered) == 2
    
    agent.register_hook(AgentHook.PRE_DISCONNECT, hook_callback)
    agent.register_hook(AgentHook.POST_DISCONNECT, hook_callback)
    
    await agent.disconnect()
    assert len(hooks_triggered) == 4


@pytest.mark.asyncio
async def test_message_middleware():
    broker = MessageBroker()
    middleware = MockMiddleware()
    broker.add_middleware(middleware)
    
    agent = Agent("agent_1", "Agent 1")
    await agent.connect(broker)
    
    message = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        recipient_id="agent_1",
        content={"test": "data"}
    )
    
    await broker.send(message)
    
    assert middleware.called
    assert middleware.processed_message.metadata["middleware_processed"] is True


@pytest.mark.asyncio
async def test_custom_validation():
    broker = MessageBroker()
    rule = MockValidationRule(succeed=False)
    broker.add_validation_rule(rule)
    
    agent = Agent("agent_1", "Agent 1")
    await agent.connect(broker)
    
    message = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        recipient_id="agent_1",
        content={"test": "data"}
    )
    
    status = await broker.send(message)
    
    assert rule.called
    assert status == MessageStatus.FAILED
    assert broker.metrics["validation_failed"] == 1


@pytest.mark.asyncio
async def test_custom_router_plugin():
    class CapabilityRouter(MessageRouter):
        def route(self, message: AgentMessage, available_agents: list) -> list:
            if message.content.get("target_capability") == "math":
                return [a for a in available_agents if "math" in a]
            return []

    broker = MessageBroker()
    router = CapabilityRouter()
    broker.set_router(router)
    
    math_received = []
    other_received = []

    async def math_handler(msg):
        math_received.append(msg)
        return {"result": "processed"}

    async def other_handler(msg):
        other_received.append(msg)
        return {"result": "processed"}

    math_agent = Agent("math_expert", "Math Expert")
    math_agent.register_handler(MessageType.NOTIFICATION, math_handler)
    await math_agent.connect(broker)
    
    other_agent = Agent("other", "Other Agent")
    other_agent.register_handler(MessageType.NOTIFICATION, other_handler)
    await other_agent.connect(broker)
    
    message = AgentMessage(
        type=MessageType.NOTIFICATION,
        sender_id="sender",
        content={"target_capability": "math", "op": "add"}
    )
    
    # Send broadcast (recipient_id=None)
    await broker.send(message)
    
    # Wait a bit for processing
    await asyncio.sleep(0.1)
    
    # Check if math_expert got it
    assert len(math_received) == 1
    assert math_received[0].content["op"] == "add"
    
    # Check if other didn't get it
    assert len(other_received) == 0
