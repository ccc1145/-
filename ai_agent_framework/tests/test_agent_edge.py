"""Agent 主循环边界测试：LLM 异常 / max_iter 边界 / JSON 剥离 / 无工具文案。

覆盖 M7（LLM 异常）、C3（最后一轮 JSON 剥离）、m-3（无工具文案）、FINALIZE_HINT 行为。
"""
import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

from ai_agent_framework.core.agent import Agent, _parse_tool_call, _strip_tool_json
from ai_agent_framework.config.settings import Settings, AgentConfig
from ai_agent_framework.tools import ToolRegistry, CalculatorTool


class _StaticRetriever:
    def __init__(self, docs):
        self._docs = docs

    def retrieve(self, query, top_k=None):
        return self._docs


class _ScriptedLLM(Runnable):
    """按预设脚本依次返回输出的 LLM。"""

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self._idx = 0

    def invoke(self, input, config=None, **kwargs):
        if self._idx >= len(self._outputs):
            # 超出脚本时返回固定回答
            return AIMessage(content="最终答案")
        out = self._outputs[self._idx]
        self._idx += 1
        if isinstance(out, Exception):
            raise out
        return AIMessage(content=out)


def _settings(max_tool_calls=2, answer_when_no_context=True):
    return Settings(agent=AgentConfig(
        max_tool_calls=max_tool_calls,
        answer_when_no_context=answer_when_no_context,
    ))


# ---- M7: LLM 异常 ----

def test_agent_llm_exception_returns_error_result():
    """LLM 调用抛异常时返回 AgentResult(answer="LLM 调用失败：...")，不抛出。"""
    llm = _ScriptedLLM([RuntimeError("API 限流")])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    agent = Agent(llm, _StaticRetriever(docs), ToolRegistry(), _settings())
    result = agent.run("any question")
    assert "LLM 调用失败" in result.answer
    assert "API 限流" in result.answer
    assert result.tool_calls == []
    assert result.source_documents == docs


def test_agent_llm_exception_in_second_round():
    """第二轮 LLM 异常也被捕获。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "1+1"}',  # 第一轮：调用工具
        RuntimeError("第二轮失败"),  # 第二轮：异常
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=3))
    result = agent.run("计算")
    assert "LLM 调用失败" in result.answer
    # 第一轮的工具调用已记录
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "calculator"


# ---- C3: 最后一轮 JSON 剥离 ----

def test_agent_final_round_strips_json_and_keeps_text():
    """最后一轮 LLM 仍输出 JSON + 正文：剥离 JSON 后保留正文。"""
    llm = _ScriptedLLM([
        # 最后一轮：JSON + 正文
        '根据已有信息回答如下：答案是 42。\n\n{"tool": "calculator", "input": "99"}',
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=0))
    result = agent.run("答案是什么")
    # 应保留正文，不含 JSON
    assert "42" in result.answer
    assert "{" not in result.answer
    assert "calculator" not in result.answer


def test_agent_final_round_pure_json_returns_fallback_text():
    """最后一轮 LLM 仅输出 JSON 无正文：使用兜底文案。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "999"}',
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=0))
    result = agent.run("x")
    # 无正文 → 兜底文案
    assert "已达到最大工具调用次数" in result.answer


# ---- m-3: 无工具注册文案 ----

def test_agent_no_tools_returns_specific_message():
    """LLM 试图调用工具但 ToolRegistry 为空：返回"未注册任何工具"文案。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "1+1"}',
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    agent = Agent(llm, _StaticRetriever(docs), ToolRegistry(), _settings(max_tool_calls=2))
    result = agent.run("计算")
    assert "未注册任何工具" in result.answer


# ---- max_iter 边界 ----

def test_agent_max_tool_calls_zero():
    """max_tool_calls=0 时，第一轮就是最后一轮，FINALIZE_HINT 应追加。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "1+1"}',  # 第一轮就触发 FINALIZE_HINT
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=0))
    result = agent.run("x")
    # 不应调用工具
    assert result.tool_calls == []


def test_agent_max_tool_calls_exactly_one():
    """max_tool_calls=1：第一轮可调用工具，第二轮强制收尾。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "2+2"}',  # 第一轮：调用工具
        '{"tool": "calculator", "input": "999"}',  # 第二轮：应被强制收尾
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=1))
    result = agent.run("计算")
    # 只调用了一次工具
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["result"] == "4"


# ---- 工具调用正常路径 ----

def test_agent_tool_call_success_then_answer():
    """工具调用成功后，下一轮 LLM 给出最终答案。"""
    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "6 * 7"}',  # 第一轮：调用工具
        "根据计算结果，答案是 42。",  # 第二轮：最终答案
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=3))
    result = agent.run("计算 6*7")
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["result"] == "42"
    assert "42" in result.answer


def test_agent_unknown_tool_returns_observation():
    """调用不存在的工具：observation 提示，下一轮 LLM 继续推理。"""
    llm = _ScriptedLLM([
        '{"tool": "nonexistent", "input": "x"}',  # 第一轮：调用不存在的工具
        "抱歉，我无法处理此请求。",  # 第二轮：最终答案
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=3))
    result = agent.run("x")
    # 不存在的工具调用不会进 tool_calls（只是 observation）
    assert result.tool_calls == []
    assert "抱歉" in result.answer


def test_agent_tool_execution_exception_caught():
    """工具执行抛异常时被捕获，作为 observation 返回。"""
    class _BoomTool(CalculatorTool):
        name = "calculator"
        description = "测试用"
        def run(self, input: str) -> str:
            raise RuntimeError("工具内部错误")

    llm = _ScriptedLLM([
        '{"tool": "calculator", "input": "1"}',  # 第一轮：调用工具（会抛异常）
        "工具出错了，我换个方式回答。",  # 第二轮：最终答案
    ])
    docs = [Document(page_content="ctx", metadata={"source": "a"})]
    reg = ToolRegistry()
    reg.register(_BoomTool())
    agent = Agent(llm, _StaticRetriever(docs), reg, _settings(max_tool_calls=3))
    result = agent.run("计算")
    assert len(result.tool_calls) == 1
    assert "工具执行出错" in result.tool_calls[0]["result"]
    assert "工具出错了" in result.answer


# ---- JSON 解析辅助函数 ----

def test_parse_tool_call_fenced_json():
    """解析 ```json 代码块中的工具调用。"""
    text = '让我算一下：\n```json\n{"tool": "calculator", "input": "1+1"}\n```\n'
    parsed = _parse_tool_call(text)
    assert parsed == {"tool": "calculator", "input": "1+1"}


def test_parse_tool_call_bare_json():
    """解析裸 JSON。"""
    text = '调用工具 {"tool": "calculator", "input": "2+2"} 完成'
    parsed = _parse_tool_call(text)
    assert parsed == {"tool": "calculator", "input": "2+2"}


def test_parse_tool_call_no_json_returns_none():
    """无 JSON 时返回 None。"""
    assert _parse_tool_call("这是普通回答") is None


def test_parse_tool_call_invalid_json_returns_none():
    """非法 JSON 时返回 None。"""
    assert _parse_tool_call('{"tool": "x"') is None


def test_strip_tool_json_fenced():
    """剥离代码块 JSON。"""
    text = '答案是 42。\n```json\n{"tool": "x", "input": "y"}\n```\n'
    stripped = _strip_tool_json(text)
    assert "42" in stripped
    assert "{" not in stripped


def test_strip_tool_json_bare():
    """剥离裸 JSON。"""
    text = '答案是 42。{"tool": "x", "input": "y"}'
    stripped = _strip_tool_json(text)
    assert "42" in stripped
    assert "{" not in stripped


def test_strip_tool_json_no_json_unchanged():
    """无 JSON 时原文返回（仅 strip）。"""
    text = "  普通回答  "
    assert _strip_tool_json(text) == "普通回答"
