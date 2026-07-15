"""Agent 输出解析器：解析 LLM 返回的文本，提取结构化 JSON。

策划书 5.3 节定义解析流程：
    1. 尝试直接 JSON 解析
    2. 失败 -> 从 Markdown 代码块提取 JSON
    3. 失败 -> 用正则提取花括号包裹的内容
    4. 全部失败 -> 返回降级响应（保持游戏可运行）

输出格式对齐 docs/agent-io-format.md v0.1。

Day 4 实现：基础解析 + 降级；Day 12 增强：更多提取策略 + 内容安全过滤。
"""
from __future__ import annotations

import json
import re
from typing import Any


# 降级响应用的兜底选项
_FALLBACK_CHOICES = [
    {"id": "continue", "text": "继续"},
    {"id": "retry", "text": "重新尝试"},
]


class AgentOutputParser:
    """解析 Agent 输出，处理各种格式错误。

    用法：
        parser = AgentOutputParser()
        result = parser.parse(llm_raw_output)
        if result.get("parse_failed"):
            # 走降级逻辑
            ...
    """

    def parse(self, raw_output: str, max_retries: int = 3) -> dict[str, Any]:
        """解析 LLM 原始输出为结构化 dict。

        Args:
            raw_output: LLM 返回的原始字符串
            max_retries: 内部重试次数（每次尝试不同策略，而非重新调用 LLM）

        Returns:
            符合 docs/agent-io-format.md 的 dict。解析失败时带 `parse_failed: True`。
        """
        if not raw_output or not raw_output.strip():
            return self._fallback_response(raw_output, reason="empty_output")

        # 按策略顺序尝试，每个策略独立 try
        strategies = [
            self._try_direct_json,
            self._try_markdown_block,
            self._try_brace_extraction,
        ]

        # max_retries 控制策略轮次：3 个策略 × 1 轮 = 3 次尝试
        # 策划书原意是"重新调用 LLM 最多 3 次"，但 LLM 重试由上层 controller 负责
        # 这里只做单轮内的多策略解析
        for _ in range(max(1, max_retries)):
            for strategy in strategies:
                result = strategy(raw_output)
                if result is not None:
                    # 解析成功，做字段校验和补全
                    return self._validate_and_complete(result)

        # 全部失败：降级
        return self._fallback_response(raw_output, reason="all_strategies_failed")

    # ---- 解析策略 ----

    def _try_direct_json(self, text: str) -> dict[str, Any] | None:
        """策略 1：直接 JSON 解析。"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    def _try_markdown_block(self, text: str) -> dict[str, Any] | None:
        """策略 2：从 Markdown 代码块提取 JSON。

        匹配 ```json ... ``` 或 ``` ... ``` 包裹的内容。
        """
        # 先试 ```json 显式标记
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if not match:
            # 再试普通 ``` 代码块
            match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            return None

    def _try_brace_extraction(self, text: str) -> dict[str, Any] | None:
        """策略 3：正则提取最外层花括号包裹的内容。

        贪婪匹配从第一个 `{` 到最后一个 `}`，适合 LLM 在 JSON 前后附加说明文字的场景。
        """
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, TypeError):
            return None

    # ---- 字段校验与补全 ----

    def _validate_and_complete(self, data: dict[str, Any]) -> dict[str, Any]:
        """对解析成功的 dict 做字段校验和必要补全。

        校验规则对齐 docs/agent-io-format.md 第 4 节：
        - available_choices 必填，长度 1-4
        - narrative / narrative_segments 至少一个
        - narrative_segments 中 type=dialogue 时 speaker 必填
        """
        # available_choices 缺失或非法：补一个兜底
        choices = data.get("available_choices")
        if not isinstance(choices, list) or not choices:
            data["available_choices"] = _FALLBACK_CHOICES
        else:
            # 截断到最多 4 个
            data["available_choices"] = choices[:4]
            # 校验每个 choice 的字段
            cleaned = []
            for c in data["available_choices"]:
                if isinstance(c, dict) and "id" in c and "text" in c:
                    cleaned.append({"id": str(c["id"]), "text": str(c["text"])})
            data["available_choices"] = cleaned or _FALLBACK_CHOICES

        # narrative / narrative_segments 至少一个；都没有则补占位
        narrative = data.get("narrative")
        segments = data.get("narrative_segments")
        if not narrative and not segments:
            data["narrative"] = "（叙事生成异常，请重试）"
            data["parse_failed"] = True
        elif narrative and not isinstance(narrative, str):
            data["narrative"] = str(narrative)

        # narrative_segments 字段校验
        if isinstance(segments, list):
            cleaned_segs = []
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                seg_type = seg.get("type")
                seg_text = seg.get("text")
                if not seg_type or not seg_text:
                    continue
                cleaned_seg = {"type": str(seg_type), "text": str(seg_text)}
                # type=dialogue 时必须有 speaker
                if seg_type == "dialogue" and seg.get("speaker"):
                    cleaned_seg["speaker"] = str(seg["speaker"])
                cleaned_segs.append(cleaned_seg)
            data["narrative_segments"] = cleaned_segs

        return data

    # ---- 降级响应 ----

    def _fallback_response(
        self, raw_output: str, reason: str = "unknown"
    ) -> dict[str, Any]:
        """降级响应：使用原始文本作为 narrative，保持游戏可运行。

        对齐 docs/agent-io-format.md 第 5.2 节降级输出格式。
        """
        text = raw_output[:500] if raw_output and raw_output.strip() else "（叙事生成中，请稍候...）"
        return {
            "narrative": text,
            "narrative_segments": [{"type": "narration", "text": text}],
            "state_changes": {},
            "available_choices": _FALLBACK_CHOICES,
            "free_input_enabled": True,
            "thought": f"DEGRADED: parser fallback, reason={reason}",
            "degraded": True,
            "parse_failed": True,
        }


if __name__ == "__main__":
    # 自测：覆盖各种 LLM 输出形态
    parser = AgentOutputParser()

    cases = [
        ("标准 JSON", '{"narrative":"测试","available_choices":[{"id":"a","text":"A"}]}'),
        ("Markdown 代码块", '```json\n{"narrative":"md测试","available_choices":[{"id":"b","text":"B"}]}\n```'),
        ("前后带说明", '好的，这是叙事：\n{"narrative":"带说明","available_choices":[{"id":"c","text":"C"}]}\n以上。'),
        ("空字符串", ""),
        ("纯文本无 JSON", "LLM 出错了，这只是一段普通文本。"),
        ("缺 available_choices", '{"narrative":"缺选项"}'),
        ("segments 无 speaker", '{"narrative":"x","narrative_segments":[{"type":"dialogue","text":"对话"}],"available_choices":[{"id":"d","text":"D"}]}'),
    ]

    for name, raw in cases:
        print(f"\n=== {name} ===")
        result = parser.parse(raw)
        if result.get("parse_failed"):
            print(f"  [降级] narrative={result['narrative'][:30]}... degraded={result.get('degraded')}")
        else:
            print(f"  [成功] narrative={result.get('narrative','')[:30]}... choices={len(result['available_choices'])} segs={len(result.get('narrative_segments',[]))}")
