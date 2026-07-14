"""响应生成器测试。"""
from langchain_core.documents import Document

from ai_agent_framework.rag.generator import ResponseGenerator, _format_context
from ai_agent_framework.core.llm import _FakeLLM


def test_format_context_empty():
    assert _format_context([]) == "（无相关上下文）"


def test_format_context_numbered():
    docs = [Document(page_content="片段A", metadata={"source": "a.txt"})]
    out = _format_context(docs)
    assert "[来源1]" in out
    assert "片段A" in out


def test_generator_returns_result_with_sources():
    gen = ResponseGenerator(_FakeLLM())
    docs = [Document(page_content="RAG 是检索增强生成", metadata={"source": "a.md"})]
    result = gen.generate("什么是 RAG？", docs)
    assert isinstance(result.answer, str)
    assert len(result.answer) > 0
    assert result.source_documents == docs


def test_generator_handles_no_context():
    gen = ResponseGenerator(_FakeLLM())
    result = gen.generate("问题", [])
    assert "无相关上下文" in result.answer or len(result.answer) > 0
