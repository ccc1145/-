"""LLM 工厂：按配置创建 LLM 实例（默认 OpenAI 兼容接口）。"""
from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

from ai_agent_framework.config.settings import LLMConfig


def get_llm(config: LLMConfig | None = None) -> Any:
    """工厂函数：返回 LLM 实例。

    默认走 OpenAI 兼容接口（DeepSeek / 智谱 / OpenAI 均可）。
    provider 为 'fake' 时返回基于关键词的假 LLM，供离线测试。
    """
    if config is None:
        from ai_agent_framework.config import get_settings

        config = get_settings().llm

    if config.provider == "fake":
        return _FakeLLM()

    if config.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    raise ValueError(f"未知的 LLM provider: {config.provider}")


class _FakeLLM(Runnable):
    """假 LLM，用于离线/测试。基于关键词的简单应答，兼容 Runnable 接口。"""

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        prompt_str = self._extract_text(input)
        lowered = prompt_str.lower()
        if "你好" in lowered or "hello" in lowered:
            content = "你好，我是基于 FakeLLM 的测试回复。"
        elif "什么是" in lowered or "what is" in lowered or "包含" in lowered:
            content = "（FakeLLM 测试回复）根据上下文，这是一个模拟答案，包含所需信息。"
        elif "计算" in lowered:
            content = f"（FakeLLM 测试回复）已收到计算请求：{prompt_str[:80]}"
        else:
            m = re.search(
                r'\{\s*"tool"\s*:\s*"([^"]+)"\s*,\s*"input"\s*:\s*"([^"]*)"\s*\}',
                prompt_str,
            )
            if m:
                content = f"已收到工具调用请求: {m.group(1)}({m.group(2)})，FakeLLM 模拟回复。"
            else:
                content = "（FakeLLM 测试回复）" + prompt_str[:80]
        return AIMessage(content=content)

    @staticmethod
    def _extract_text(input: Any) -> str:
        if isinstance(input, str):
            return input
        # ChatPromptValue / 走 to_string
        for attr in ("to_string", "to_messages"):
            fn = getattr(input, attr, None)
            if callable(fn):
                try:
                    val = fn()
                    if isinstance(val, str):
                        return val
                    if isinstance(val, list):
                        return "\n".join(
                            m.content if hasattr(m, "content") else str(m) for m in val
                        )
                except Exception:
                    continue
        return str(input)
