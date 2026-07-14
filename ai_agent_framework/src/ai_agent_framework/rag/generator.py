"""响应生成器：结合检索上下文与查询，调用 LLM 生成回答。"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

DEFAULT_SYSTEM_PROMPT = """你是一个严谨的知识问答助手。请根据下方检索到的上下文回答用户问题。
规则：
1. 答案必须基于上下文，不得编造。
2. 若上下文不足以回答，请明确说明"根据现有资料无法回答"。
3. 回答末尾用 [来源N] 标注引用的上下文编号。
"""

DEFAULT_USER_TEMPLATE = """检索上下文：
{context}

用户问题：{question}

请给出回答："""


@dataclass
class GenerationResult:
    answer: str
    source_documents: list[Document]


def _format_context(documents: list[Document]) -> str:
    """将检索文档格式化为编号上下文块。"""
    if not documents:
        return "（无相关上下文）"
    parts = []
    for i, d in enumerate(documents, 1):
        src = d.metadata.get("source", "未知")
        parts.append(f"[来源{i}] 来源: {src}\n{d.page_content}")
    return "\n\n".join(parts)


class ResponseGenerator:
    """响应生成器：构造 prompt 并调用 LLM。

    可通过 system_prompt / user_template 自定义提示词。
    """

    def __init__(
        self,
        llm,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        user_template: str = DEFAULT_USER_TEMPLATE,
    ):
        self._llm = llm
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", user_template)]
        )

    def generate(self, query: str, documents: list[Document]) -> GenerationResult:
        context = _format_context(documents)
        chain = self._prompt | self._llm
        response = chain.invoke({"context": context, "question": query})
        answer = response.content if hasattr(response, "content") else str(response)
        return GenerationResult(answer=answer, source_documents=documents)
