"""内置工具：计算器、知识检索。"""
from __future__ import annotations

import ast
import operator

from ai_agent_framework.tools.base import Tool


class CalculatorTool(Tool):
    """安全算术计算器，支持 + - * / ** % () 与数字。"""

    name = "calculator"
    description = "算术表达式求值。输入形如 '2 + 3 * 4' 的数学表达式，返回计算结果。"

    _OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.FloorDiv: operator.floordiv,
    }

    def run(self, input: str) -> str:
        expr = input.strip()
        if not expr:
            return "错误：表达式为空"
        try:
            tree = ast.parse(expr, mode="eval")
            result = self._eval(tree.body)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"

    def _eval(self, node: ast.AST):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, tuple(self._OPS)):
            return self._OPS[type(node.op)](self._eval(node.left), self._eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, tuple(self._OPS)):
            return self._OPS[type(node.op)](self._eval(node.operand))
        raise ValueError("不支持的表达式")


class KnowledgeSearchTool(Tool):
    """封装检索器的知识检索工具，供 Agent 在需要时调用。"""

    name = "knowledge_search"
    description = "在知识库中检索与查询相关的资料。输入检索关键词或问题，返回相关文档片段。"

    def __init__(self, retriever, top_k: int = 4):
        self._retriever = retriever
        self._top_k = top_k

    def run(self, input: str) -> str:
        docs = self._retriever.retrieve(input, top_k=self._top_k)
        if not docs:
            return "未检索到相关资料。"
        parts = []
        for i, d in enumerate(docs, 1):
            src = d.metadata.get("source", "未知")
            parts.append(f"[{i}] (来源: {src}) {d.page_content}")
        return "\n\n".join(parts)
