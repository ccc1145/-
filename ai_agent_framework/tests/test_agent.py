"""Agent 主循环测试。"""
import pytest
from langchain_core.documents import Document

from ai_agent_framework.core.agent import Agent
from ai_agent_framework.core.llm import _FakeLLM
from ai_agent_framework.config.settings import Settings, AgentConfig
from ai_agent_framework.tools import ToolRegistry, CalculatorTool


class _StaticRetriever:
    def __init__(self, docs):
        self._docs = docs

    def retrieve(self, query, top_k=None):
        return self._docs


def _settings():
    return Settings(agent=AgentConfig(max_tool_calls=2))


def test_agent_run_basic():
    docs = [Document(page_content="RAG 结合检索与生成", metadata={"source": "a.md"})]
    agent = Agent(_FakeLLM(), _StaticRetriever(docs), ToolRegistry(), _settings())
    result = agent.run("什么是 RAG")
    assert isinstance(result.answer, str)
    assert len(result.answer) > 0
    assert result.source_documents == docs
    assert result.tool_calls == []


def test_agent_with_tools_registered():
    docs = [Document(page_content="上下文", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(_FakeLLM(), _StaticRetriever(docs), reg, _settings())
    result = agent.run("计算 2+2")
    assert result.answer
    # 工具是否被调用取决于 FakeLLM 是否输出 JSON；这里仅验证不抛错


def test_agent_result_structure():
    docs = []
    agent = Agent(_FakeLLM(), _StaticRetriever(docs), ToolRegistry(), _settings())
    r = agent.run("hello")
    assert hasattr(r, "answer")
    assert hasattr(r, "source_documents")
    assert hasattr(r, "tool_calls")
    assert hasattr(r, "raw")


def test_agent_answer_when_no_context_disabled():
    """M-4：当 answer_when_no_context=False 且检索为空时，不应调用 LLM。"""
    settings = Settings(agent=AgentConfig(max_tool_calls=2, answer_when_no_context=False))
    call_count = {"n": 0}

    class _CountingLLM(_FakeLLM):
        def invoke(self, input, config=None, **kwargs):
            call_count["n"] += 1
            return super().invoke(input, config=config, **kwargs)

    agent = Agent(_CountingLLM(), _StaticRetriever([]), ToolRegistry(), settings)
    result = agent.run("any question")
    assert call_count["n"] == 0
    assert "未检索到相关上下文" in result.answer


def test_agent_answer_when_no_context_enabled():
    """对照：answer_when_no_context=True（默认）时仍调用 LLM。"""
    settings = Settings(agent=AgentConfig(max_tool_calls=2, answer_when_no_context=True))
    call_count = {"n": 0}

    class _CountingLLM(_FakeLLM):
        def invoke(self, input, config=None, **kwargs):
            call_count["n"] += 1
            return super().invoke(input, config=config, **kwargs)

    agent = Agent(_CountingLLM(), _StaticRetriever([]), ToolRegistry(), settings)
    agent.run("any question")
    assert call_count["n"] >= 1
