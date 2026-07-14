"""核心控制模块：协议定义、注册中心、Agent 主循环。"""
from ai_agent_framework.core.base import (
    DocumentLoaderProtocol,
    SplitterProtocol,
    EmbeddingsProtocol,
    VectorStoreProtocol,
    RetrieverProtocol,
    LLMProtocol,
    ToolProtocol,
)
from ai_agent_framework.core.registry import ComponentRegistry, get_registry
from ai_agent_framework.core.agent import Agent, AgentResult

__all__ = [
    "DocumentLoaderProtocol",
    "SplitterProtocol",
    "EmbeddingsProtocol",
    "VectorStoreProtocol",
    "RetrieverProtocol",
    "LLMProtocol",
    "ToolProtocol",
    "ComponentRegistry",
    "get_registry",
    "Agent",
    "AgentResult",
]
