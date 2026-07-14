"""工具调用接口测试。"""
import pytest

from ai_agent_framework.tools import ToolRegistry, CalculatorTool, KnowledgeSearchTool
from ai_agent_framework.tools.base import Tool


def test_calculator_basic():
    calc = CalculatorTool()
    assert calc.run("2 + 3") == "5"
    assert calc.run("(2 + 3) * 4") == "20"
    assert calc.run("2 ** 10") == "1024"
    assert calc.run("10 / 4").startswith("2.5")


def test_calculator_invalid():
    calc = CalculatorTool()
    out = calc.run("__import__('os')")
    assert "计算错误" in out or "不支持" in out
    out2 = calc.run("")
    assert "空" in out2


def test_tool_registry_register_and_call():
    reg = ToolRegistry()
    calc = CalculatorTool()
    reg.register(calc)
    assert reg.has("calculator")
    assert reg.call("calculator", "1 + 1") == "2"
    names = reg.names()
    assert "calculator" in names


def test_tool_registry_missing():
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.get("nope")


def test_tool_registry_list():
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    info = reg.list()
    assert info[0]["name"] == "calculator"
    assert info[0]["description"]


class _FakeRetriever:
    def retrieve(self, query, top_k=None):
        from langchain_core.documents import Document

        return [Document(page_content=f"关于{query}的资料", metadata={"source": "fake"})]


def test_knowledge_search_tool():
    tool = KnowledgeSearchTool(_FakeRetriever(), top_k=2)
    out = tool.run("AI")
    assert "AI" in out
    assert "来源" in out
