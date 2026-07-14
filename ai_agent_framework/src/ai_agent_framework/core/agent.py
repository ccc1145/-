"""Agent 主循环：检索 → 工具决策 → 生成，支持 ReAct 风格的工具调用。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from ai_agent_framework.config.settings import Settings
from ai_agent_framework.core.base import RetrieverProtocol
from ai_agent_framework.tools.base import ToolRegistry

logger = logging.getLogger(__name__)

REACT_SYSTEM_PROMPT = """你是一个能调用工具的知识型 Agent。可按以下流程作答：

1. 思考（Thought）：分析问题，决定是否需要调用工具。
2. 行动（Action）：若需要工具，输出一行 JSON：
   {{"tool": "工具名", "input": "工具输入"}}
   若无需工具，直接给出最终答案。
3. 观察（Observation）：工具返回结果（系统填入）。
4. 重复直到能给出最终答案。

可用工具：
{tools}

可用知识上下文（检索自知识库）：
{context}

输出格式要求：
- 调用工具时，单独一行输出合法 JSON，不要附加多余文字。
- 给出最终答案时，直接输出答案正文，并在末尾用 [来源N] 标注引用。
"""

# 最终轮追加提示，强制 LLM 收尾而非继续调用工具
FINALIZE_HINT = "\n\n[系统提示] 已达到最大工具调用次数，请直接给出最终答案，不要再输出工具调用 JSON。"


@dataclass
class AgentResult:
    answer: str
    source_documents: list[Document]
    tool_calls: list[dict[str, str]]
    raw: str = ""


def _parse_tool_call(text: str) -> dict[str, str] | None:
    """从 LLM 输出中解析工具调用 JSON，支持代码块与裸 JSON。"""
    # 1) 优先尝试提取 ```json ... ``` 代码块
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if fence:
        candidates.append(fence.group(1))
    # 2) 正则匹配裸 JSON
    candidates.extend(_TOOL_JSON_RE.findall(text))
    for cand in candidates:
        parsed = _try_json(cand)
        if parsed and "tool" in parsed:
            return {"tool": str(parsed["tool"]), "input": str(parsed.get("input", ""))}
    return None


def _try_json(s: str) -> dict | None:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _strip_tool_json(text: str) -> str:
    """剥离文本中的工具调用 JSON（代码块或裸 JSON），保留剩余正文。"""
    # 剥离 ```json ... ``` 代码块
    out = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.DOTALL)
    # 剥离裸 JSON
    out = _TOOL_JSON_RE.sub("", out)
    return out.strip()


# 裸 JSON 正则（捕获整组用于 json.loads 解析）
_TOOL_JSON_RE = re.compile(r'\{[^{}]*"tool"[^{}]*\}')


class Agent:
    """Agent：持有 LLM、检索器、工具注册中心，执行感知-推理-行动循环。

    单轮问答为主；多轮对话可作为子类扩展点（维护 history）。
    """

    def __init__(
        self,
        llm: Any,
        retriever: RetrieverProtocol,
        tool_registry: ToolRegistry | None = None,
        settings: Settings | None = None,
    ):
        self._llm = llm
        self._retriever = retriever
        self._tools = tool_registry or ToolRegistry()
        self._settings = settings or self._load_settings()
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", REACT_SYSTEM_PROMPT), ("human", "{question}")]
        )

    @staticmethod
    def _load_settings() -> Settings:
        from ai_agent_framework.config import get_settings

        return get_settings()

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    def run(self, query: str) -> AgentResult:
        """执行一次问答。"""
        # 1. 检索知识上下文
        try:
            docs = self._retriever.retrieve(query)
        except Exception as e:  # noqa: BLE001
            logger.warning("检索失败: %s", e)
            docs = []

        # 配置：检索为空时是否仍调用 LLM 生成回答
        if not docs and not self._settings.agent.answer_when_no_context:
            return AgentResult(
                answer="未检索到相关上下文，且当前配置不允许在无上下文时生成回答。",
                source_documents=[],
                tool_calls=[],
                raw="",
            )

        context = self._format_context(docs)

        tools_desc = self._format_tools()
        chain = self._prompt | self._llm
        tool_calls: list[dict[str, str]] = []
        observation = ""
        max_iter = self._settings.agent.max_tool_calls
        final_answer = ""
        raw = ""

        for iteration in range(max_iter + 1):
            user_msg = query
            if observation:
                user_msg += f"\n\n[上一轮观察]\n{observation}"
            # 最后一轮强制收尾
            if iteration == max_iter and max_iter > 0:
                user_msg += FINALIZE_HINT

            try:
                response = chain.invoke(
                    {"tools": tools_desc, "context": context, "question": user_msg}
                )
            except Exception as e:  # noqa: BLE001
                logger.error("LLM 调用失败: %s", e)
                return AgentResult(
                    answer=f"LLM 调用失败：{e}",
                    source_documents=docs,
                    tool_calls=tool_calls,
                    raw="",
                )
            raw = response.content if hasattr(response, "content") else str(response)

            tool_call = _parse_tool_call(raw)
            can_call_tool = bool(iteration < max_iter and self._tools.names())

            if tool_call and can_call_tool:
                tool_name = tool_call["tool"]
                tool_input = tool_call["input"]
                if self._tools.has(tool_name):
                    try:
                        result = self._tools.call(tool_name, tool_input)
                    except Exception as e:  # noqa: BLE001
                        result = f"工具执行出错: {e}"
                    tool_calls.append(
                        {"tool": tool_name, "input": tool_input, "result": result}
                    )
                    observation = result
                    continue
                else:
                    observation = f"工具 {tool_name} 不存在"
                    continue

            # 无工具调用 → 视为最终答案
            # 但若仍含工具 JSON（无法继续调用工具），剥离 JSON 后保留 LLM 已生成的正文
            if tool_call and not can_call_tool:
                stripped = _strip_tool_json(raw)
                if stripped.strip():
                    final_answer = stripped.strip()
                elif not self._tools.names():
                    final_answer = "Agent 试图调用工具但当前未注册任何工具。"
                else:
                    final_answer = (
                        "已达到最大工具调用次数，基于现有信息无法继续调用工具。"
                        "请尝试简化问题或增大 max_tool_calls 配置。"
                    )
            else:
                final_answer = raw
            break
        else:
            # 理论不可达（循环内必 break），兜底
            final_answer = raw or "Agent 未能生成回答。"

        return AgentResult(
            answer=final_answer,
            source_documents=docs,
            tool_calls=tool_calls,
            raw=raw,
        )

    @staticmethod
    def _format_context(documents: list[Document]) -> str:
        if not documents:
            return "（无相关上下文）"
        parts = []
        for i, d in enumerate(documents, 1):
            src = d.metadata.get("source", "未知")
            parts.append(f"[来源{i}] ({src}) {d.page_content}")
        return "\n\n".join(parts)

    def _format_tools(self) -> str:
        tools = self._tools.list()
        if not tools:
            return "（无可用工具）"
        lines = [f"- {t['name']}: {t['description']}" for t in tools]
        return "\n".join(lines)
