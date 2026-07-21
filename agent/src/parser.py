"""Agent 输出解析器：解析 LLM 返回的文本，提取结构化 JSON。

策划书 5.3 节定义解析流程：
    1. 尝试直接 JSON 解析
    2. 失败 -> 从 Markdown 代码块提取 JSON
    3. 失败 -> 用正则提取花括号包裹的内容
    4. 全部失败 -> 返回降级响应（保持游戏可运行）

输出格式对齐 docs/agent-io-format.md v1.0。

Day 4 实现：基础解析 + 降级
Day 6-7 Polish 增强：
  - 字段名大小写归一化（LLM 偶尔返回 Narrative 而非 narrative）
  - 中文标点转英文（"" '' ，）
  - narrative 为 list 时的合并处理
  - 花括号提取改为平衡匹配，避免嵌套 JSON 被截断
  - 单引号 JSON 容错（部分 LLM 用单引号）
Day 12 增强：
  - 嵌套对象提取（LLM 返回 {"data": {...}} / {"result": {...}}）
  - 多行 JSON 拼接（LLM 把 JSON 拆成多段输出）
  - 数值字段类型校验（hp/cultivation 应为 int，不能是 string）
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

# 字段名归一化映射（处理 LLM 返回的大小写/下划线变体）
# 归一化策略：key 转小写 + 驼峰转下划线后匹配（更稳健）
_FIELD_ALIASES = {
    "narrative": ["narrative", "story", "text"],
    "narrative_segments": ["narrative_segments", "segments"],
    "available_choices": ["available_choices", "choices", "options"],
    "free_input_enabled": ["free_input_enabled", "allow_free_input"],
    "thought": ["thought", "reasoning", "internal_thought"],
    "degraded": ["degraded"],
    "parse_failed": ["parse_failed"],
}

# available_choices 子字段名归一化（Day 11 新增：处理 choice_id / choice_text 等变体）
_CHOICE_FIELD_ALIASES = {
    "id": ["id", "choice_id", "key", "value"],
    "text": ["text", "choice_text", "label", "content", "description"],
}

# narrative_segments.type 允许的枚举值（对齐 docs/agent-io-format.md）
# 非标准值会被归一化为 narration
_VALID_SEGMENT_TYPES = {"narration", "dialogue", "thought", "action"}

# 输出白名单：解析成功后只保留这些字段，过滤 LLM 返回的额外字段（如 reasoning / explanation）
# Day 11 新增：避免非 schema 字段污染下游
_OUTPUT_WHITELIST = {
    "narrative",
    "narrative_segments",
    "available_choices",
    "state_changes",
    "free_input_enabled",
    "thought",
    "npc_reactions",
    # 降级标记由 parser/controller 内部设置，不在白名单过滤范围内
    "degraded",
    "parse_failed",
    # 自由输入附加字段（Day 8）
    "intent",
    "is_ooc",
    "ooc_reason",
}

# 中文标点 -> 英文标点（JSON 解析前预处理）
_PUNCT_MAP = {
    "\u201c": '"',  # "
    "\u201d": '"',  # "
    "\u2018": "'",  # '
    "\u2019": "'",  # '
    "\u3001": ",",  # 、（仅限 JSON 内部，这里保守只替换引号）
}


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
            self._try_nested_object,  # Day 12: 嵌套对象提取
            self._try_multiline_json,  # Day 12: 多行 JSON 拼接
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
        """策略 1：直接 JSON 解析。

        Day 12 增强：如果解析成功但结果是嵌套对象（只有包装字段如 data/result），
        返回 None 让后续策略提取内层对象。
        """
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        # Day 12: 检测是否为纯包装对象（如 {"data": {...}}）
        if isinstance(data, dict):
            wrapper_keys = {"data", "result", "response", "output", "content", "payload"}
            data_keys = {self._to_snake_case(k) for k in data.keys()}
            # 如果只有包装字段且没有标准字段，让嵌套策略处理
            standard_keys = {"narrative", "available_choices", "narrative_segments"}
            if data_keys & wrapper_keys and not (data_keys & standard_keys):
                return None
        return data

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
        r"""策略 3：平衡花括号匹配，提取最外层完整的 JSON 对象。

        旧版用贪婪正则 `\{.*\}`，遇到 JSON 前后有干扰的 `{}` 会被截断。
        新版改为扫描计数，找到第一个平衡的 `{...}` 块。
        """
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    # 先做标点清洗
                    cleaned = self._normalize_punctuation(candidate)
                    try:
                        return json.loads(cleaned)
                    except (json.JSONDecodeError, TypeError):
                        # 尝试单引号容错
                        try:
                            return json.loads(cleaned.replace("'", '"'))
                        except (json.JSONDecodeError, TypeError):
                            return None
        return None

    def _try_nested_object(self, text: str) -> dict[str, Any] | None:
        """策略 4（Day 12 新增）：嵌套对象提取。

        部分LLM会把结果包在外层对象里，如：
        - {"data": {...}}
        - {"result": {...}}
        - {"response": {...}}
        - {"output": {...}}

        本策略先用平衡花括号提取外层 JSON，再检查是否含已知包装字段。
        """
        outer = self._try_brace_extraction(text)
        if not isinstance(outer, dict):
            return None

        # 已知的包装字段名
        wrapper_keys = {"data", "result", "response", "output", "content", "payload"}
        for key in wrapper_keys:
            inner = outer.get(key)
            if isinstance(inner, dict):
                # 内层对象应包含 narrative 或 available_choices 等标准字段
                inner_keys = {self._to_snake_case(k) for k in inner.keys()}
                if "narrative" in inner_keys or "available_choices" in inner_keys:
                    return inner
        return None

    def _try_multiline_json(self, text: str) -> dict[str, Any] | None:
        """策略 5（Day 12 新增）：多行 JSON 拼接。

        部分LLM（特别是推理模型）会在思考过程中输出多段 JSON 碎片：
        ```
        好的，我来生成：
        {"narrative": "前半段
        ```
        （中间是思考过程）
        ```
        叙事内容","available_choices":[...]}
        ```

        本策略尝试：
        1. 提取所有 {...} 片段
        2. 按出现顺序拼接
        3. 尝试解析拼接后的完整 JSON
        """
        # 找到所有可能的 JSON 片段（含未闭合的）
        # 简化策略：把所有 { 和 } 之间的内容按顺序拼接
        # 但只保留第一次出现 { 到最后一次 } 之间的内容
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
            return None

        # 提取从第一个 { 到最后一个 } 的所有内容
        # 过滤掉中间的非 JSON 文本（如思考过程）
        candidate = text[first_brace : last_brace + 1]

        # 尝试移除可能的换行和空格干扰，重新拼接
        # 如果候选文本本身就是合法 JSON，直接返回
        cleaned = self._normalize_punctuation(candidate)
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试单引号容错
        try:
            return json.loads(cleaned.replace("'", '"'))
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试移除 JSON 中间的非 JSON 文本
        # 策略：找到所有 "key": value 模式，重新构建 JSON
        # 但这比较复杂，MVP 阶段先返回 None，让上层降级
        return None

    # ---- 字段校验与补全 ----

    def _validate_and_complete(self, data: dict[str, Any]) -> dict[str, Any]:
        """对解析成功的 dict 做字段校验和必要补全。

        校验规则对齐 docs/agent-io-format.md 第 4 节：
        - available_choices 必填，长度 1-4
        - narrative / narrative_segments 至少一个
        - narrative_segments 中 type=dialogue 时 speaker 必填

        Day 11 增强：
        - available_choices 子字段名归一化（choice_id -> id, choice_text -> text）
        - narrative_segments.type 枚举校验（非标准值归一化为 narration）
        - 输出白名单过滤（删除 LLM 返回的非 schema 字段，如 reasoning / explanation）
        Day 12 增强：
        - 嵌套对象自动展开（检测 {"data": {...}} 等包装结构）
        - 数值字段类型校验（hp/cultivation 应为 int）
        """
        # Day 12: 嵌套对象自动展开
        data = self._unwrap_nested_object(data)

        # 字段名归一化（处理 Narrative / narrativeSegments 等大小写变体）
        data = self._normalize_field_names(data)

        # available_choices 缺失或非法：补一个兜底
        choices = data.get("available_choices")
        if not isinstance(choices, list) or not choices:
            data["available_choices"] = _FALLBACK_CHOICES
        else:
            # 截断到最多 4 个
            data["available_choices"] = choices[:4]
            # 校验每个 choice 的字段（Day 11: 子字段名归一化）
            cleaned = []
            for c in data["available_choices"]:
                if not isinstance(c, dict):
                    continue
                normalized_c = self._normalize_choice_fields(c)
                if normalized_c:
                    cleaned.append(normalized_c)
            data["available_choices"] = cleaned or _FALLBACK_CHOICES

        # narrative / narrative_segments 至少一个；都没有则补占位
        narrative = data.get("narrative")
        segments = data.get("narrative_segments")
        if not narrative and not segments:
            data["narrative"] = "（叙事生成异常，请重试）"
            data["parse_failed"] = True
        elif narrative and not isinstance(narrative, str):
            # narrative 为 list（部分 LLM 会返回段落数组）-> 合并为一段
            if isinstance(narrative, list):
                data["narrative"] = "\n".join(str(x) for x in narrative if x)
            else:
                data["narrative"] = str(narrative)

        # narrative_segments 字段校验（Day 11: type 枚举校验）
        if isinstance(segments, list):
            cleaned_segs = []
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                seg_type = seg.get("type")
                seg_text = seg.get("text")
                if not seg_type or not seg_text:
                    continue
                # Day 11: type 枚举校验，非标准值归一化为 narration
                seg_type_str = str(seg_type).lower()
                if seg_type_str not in _VALID_SEGMENT_TYPES:
                    seg_type_str = "narration"
                cleaned_seg = {"type": seg_type_str, "text": str(seg_text)}
                # type=dialogue 时必须有 speaker
                if seg_type_str == "dialogue" and seg.get("speaker"):
                    cleaned_seg["speaker"] = str(seg["speaker"])
                cleaned_segs.append(cleaned_seg)
            data["narrative_segments"] = cleaned_segs

        # Day 12: 数值字段类型校验（state_changes 中的 hp/cultivation 等应为 int）
        state_changes = data.get("state_changes")
        if isinstance(state_changes, dict):
            data["state_changes"] = self._coerce_numeric_fields(state_changes)

        # Day 11: 白名单过滤，删除 LLM 返回的非 schema 字段
        data = self._apply_whitelist(data)

        return data

    @staticmethod
    def _coerce_numeric_fields(data: dict[str, Any]) -> dict[str, Any]:
        """数值字段类型校验（Day 12 新增）。

        LLM 偶尔会返回字符串形式的数值（如 "100" 而非 100）。
        本方法递归遍历 state_changes，把数值字符串转为 int/float。
        """
        if not isinstance(data, dict):
            return data
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = AgentOutputParser._coerce_numeric_fields(value)
            elif isinstance(value, list):
                result[key] = [
                    AgentOutputParser._coerce_numeric_fields(v) if isinstance(v, dict) else v
                    for v in value
                ]
            elif isinstance(value, str):
                # 尝试转 int
                try:
                    result[key] = int(value)
                    continue
                except ValueError:
                    pass
                # 尝试转 float
                try:
                    result[key] = float(value)
                    continue
                except ValueError:
                    pass
                result[key] = value
            else:
                result[key] = value
        return result

    @staticmethod
    def _normalize_choice_fields(choice: dict[str, Any]) -> dict[str, str] | None:
        """归一化 available_choices 子字段名（Day 11 新增）。

        处理 LLM 返回的变体：choice_id -> id, choice_text -> text, label -> text 等。
        """
        result: dict[str, str] = {}
        for standard, aliases in _CHOICE_FIELD_ALIASES.items():
            alias_set = {AgentOutputParser._to_snake_case(a) for a in aliases}
            for key, value in choice.items():
                normalized_key = AgentOutputParser._to_snake_case(key)
                if normalized_key in alias_set or normalized_key == standard:
                    if value:  # 非空才接受
                        result[standard] = str(value)
                        break
        # 必须同时有 id 和 text 才算有效
        if "id" in result and "text" in result:
            return result
        return None

    @staticmethod
    def _unwrap_nested_object(data: dict[str, Any]) -> dict[str, Any]:
        """嵌套对象自动展开（Day 12 新增）。

        检测 LLM 返回的包装结构，如 {"data": {...}} / {"result": {...}}，
        自动展开为内层对象（如果内层含标准字段）。
        """
        if not isinstance(data, dict):
            return data

        wrapper_keys = {"data", "result", "response", "output", "content", "payload"}
        standard_keys = {"narrative", "available_choices", "narrative_segments"}

        # 检查是否为纯包装对象
        data_keys = {AgentOutputParser._to_snake_case(k) for k in data.keys()}
        has_wrapper = bool(data_keys & wrapper_keys)
        has_standard = bool(data_keys & standard_keys)

        # 如果只有包装字段且没有标准字段，尝试展开
        if has_wrapper and not has_standard:
            for key in wrapper_keys:
                # 原始 key 可能是驼峰，需要检查
                for orig_key, inner in data.items():
                    if AgentOutputParser._to_snake_case(orig_key) == key and isinstance(inner, dict):
                        inner_keys = {AgentOutputParser._to_snake_case(k) for k in inner.keys()}
                        if inner_keys & standard_keys:
                            return inner
        return data

    @staticmethod
    def _apply_whitelist(data: dict[str, Any]) -> dict[str, Any]:
        """应用输出白名单，过滤非 schema 字段（Day 11 新增）。

        保留 _OUTPUT_WHITELIST 中的字段，删除其他（如 LLM 返回的 reasoning / explanation）。
        降级标记（degraded / parse_failed）始终保留。
        """
        return {
            k: v for k, v in data.items()
            if k in _OUTPUT_WHITELIST or k in ("degraded", "parse_failed")
        }

    # ---- 辅助方法 ----

    @staticmethod
    def _normalize_punctuation(text: str) -> str:
        """中文引号转英文引号，避免 JSON 解析失败。"""
        for cn, en in _PUNCT_MAP.items():
            text = text.replace(cn, en)
        return text

    @staticmethod
    def _normalize_field_names(data: dict[str, Any]) -> dict[str, Any]:
        """字段名归一化：把 LLM 返回的变体名映射到标准名。

        策略：把 key 转小写 + 驼峰转下划线，然后与别名表（已转小写）匹配。
        例如 Narrative -> narrative, narrativeSegments -> narrative_segments,
                 AvailableChoices -> available_choices
        只处理顶层字段，不递归。
        """
        result = {}
        for key, value in data.items():
            normalized_key = AgentOutputParser._to_snake_case(key)
            matched = False
            for standard, aliases in _FIELD_ALIASES.items():
                # 别名也转 snake_case 后比较
                alias_set = {AgentOutputParser._to_snake_case(a) for a in aliases}
                if normalized_key in alias_set or normalized_key == standard:
                    result[standard] = value
                    matched = True
                    break
            if not matched:
                result[key] = value
        return result

    @staticmethod
    def _to_snake_case(s: str) -> str:
        """驼峰转下划线：narrativeSegments -> narrative_segments。
        同时处理大写开头：Narrative -> narrative。
        """
        # 先转小写驼峰为下划线
        import re as _re
        s = _re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()
        return s

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
