"""LLM 适配层：复用 ai_agent_framework 的 get_llm，封装为叙事生成接口。

设计说明：
- 框架的 get_llm() 已统一了 OpenAI 兼容接口（DeepSeek/智谱/OpenAI 均可），
  并提供 _FakeLLM 用于离线测试，这里只做一层薄包装。
- 对外暴露 generate(system_prompt, user_prompt) -> str，屏蔽 langchain 消息细节，
  让上层 Prompt Builder / Narrative Controller 只关心字符串。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ai_agent_framework.config.settings import LLMConfig
from ai_agent_framework.core.llm import get_llm

logger = logging.getLogger(__name__)


class NarrativeLLMAdapter:
    """叙事 LLM 适配器。

    用法：
        adapter = NarrativeLLMAdapter(llm_config)   # 传 None 则读框架默认配置
        text = adapter.generate(system_prompt, user_prompt)
    """

    def __init__(self, llm_config: LLMConfig | None = None) -> None:
        # 直接复用框架工厂；provider="fake" 时返回 _FakeLLM，可离线运行
        self._llm = get_llm(llm_config)
        self._llm_config = llm_config

    @property
    def is_fake(self) -> bool:
        """是否运行在离线 FakeLLM 模式（便于上层做降级判断）。"""
        return self._llm_config is not None and self._llm_config.provider == "fake"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 生成叙事文本。

        Args:
            system_prompt: 系统提示（角色设定、世界观、核心规则）
            user_prompt:   用户提示（当前 GameState、玩家操作、需要表达的变化）

        Returns:
            LLM 输出的纯文本（通常是 JSON 字符串，由 parser.py 负责解析）。
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = self._llm.invoke(messages)
        # 复用 _extract_content，统一处理各种字段位置
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: Any) -> str:
        """从 langchain AIMessage / 框架 _FakeLLM 响应中提取文本内容。

        推理模型（如 MiMo、DeepSeek-R1）可能把内容放在不同字段：
        - content: 标准字段（普通模型用这个）
        - additional_kwargs.reasoning_content: 部分推理模型的思考过程
        - response_metadata.reasoning_content: 另一些 SDK 的位置

        策略：优先返回 content；为空时依次尝试其他字段；都为空才返回空串。
        """
        # 1. 标准字段
        content = getattr(response, "content", None)
        if content:
            return content

        # 2. 推理模型兜底：additional_kwargs.reasoning_content
        additional = getattr(response, "additional_kwargs", None) or {}
        reasoning = additional.get("reasoning_content") or additional.get("reasoning")
        if reasoning:
            logger.debug("LLM content 为空，使用 additional_kwargs.reasoning_content 兜底")
            return reasoning

        # 3. 再兜底：response_metadata 里的 reasoning_content
        metadata = getattr(response, "response_metadata", None) or {}
        reasoning_meta = metadata.get("reasoning_content") or metadata.get("reasoning")
        if reasoning_meta:
            logger.debug("LLM content 为空，使用 response_metadata.reasoning_content 兜底")
            return reasoning_meta

        # 4. 实在没有，返回空串（上层 parser 会触发降级）
        logger.warning("LLM 响应所有内容字段均为空，原始 response: %r", response)
        return ""
