"""内容安全过滤（Day 12）。

策划书 Day 12 任务 2：加入内容安全过滤（敏感词过滤）。

设计：
- 双向过滤：既检查玩家输入，也检查 LLM 输出
- 玩家输入命中敏感词：标记后由 controller 决定是否拒绝/降级
- LLM 输出命中敏感词：直接触发降级，不展示给玩家
- 敏感词分三级：blocked（硬阻断）/ warned（软警告）/ replaced（替换）

敏感词分类（MVP 阶段简化版）：
- political：政治敏感词（blocked）
- explicit：色情低俗词（blocked）
- violence：极端暴力词（warned）
- modern_slang：现代网络用语（replaced，对齐 system_prompt.j2 禁忌词清单）
- advertising：广告引流词（blocked）
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---- 敏感词清单 ----

# 政治敏感词（blocked - 硬阻断，触发降级）
# MVP 阶段只列少量示例，生产环境应从外部词库加载
_POLITICAL_WORDS: list[str] = [
    # 领导人姓名相关（示例，实际应更完整）
    "习近平", "毛泽东", "邓小平", "江泽民", "胡锦涛",
    # 政治事件
    "六四", "天安门事件", "文化大革命",
    # 政治口号
    "光复", "革命", "推翻",
]

# 色情低俗词（blocked）
_EXPLICIT_WORDS: list[str] = [
    "做爱", "性交", "操你", "日你", "草泥马",
    "鸡巴", "屌丝", "傻逼", "脑残", "废物",
    "婊子", "妓女", "强奸",
]

# 极端暴力词（warned - 软警告）
_VIOLENCE_WORDS: list[str] = [
    "杀人", "自杀", "上吊", "割腕",
    "炸弹", "恐怖袭击",
]

# 现代网络用语 / 出戏词（replaced - 替换为古风词）
# 对齐 system_prompt.j2 禁忌词清单
_MODERN_SLANG_WORDS: list[str] = [
    "666", "大佬", "小哥哥", "小姐姐", "老铁",
    "ok", "cool", "nice", "wow", "yeah",
    "手机", "电脑", "网络", "快递", "外卖",
    "支付宝", "微信", "抖音", "快手",
    "emo", "卷", "躺平", "摆烂",
]

# 广告引流词（blocked）
_ADVERTISING_WORDS: list[str] = [
    "加微信", "加QQ", "免费领取", "点击链接",
    "http://", "https://", "www.",
]


# ---- 替换映射（modern_slang 替换为古风词）----
_REPLACEMENT_MAP: dict[str, str] = {
    "666": "了得",
    "大佬": "前辈",
    "小哥哥": "公子",
    "小姐姐": "姑娘",
    "老铁": "道友",
    "ok": "善",
    "cool": "不凡",
    "nice": "妙哉",
    "wow": "咦",
    "yeah": "然也",
    "手机": "传音符",
    "电脑": "玉简",
    "网络": "灵网",
    "快递": "飞剑传书",
    "外卖": "灵膳",
    "支付宝": "灵石",
    "微信": "传讯",
    "抖音": "幻影阵",
    "快手": "瞬影术",
    "emo": "心魔",
    "卷": "争竞",
    "躺平": "闭关",
    "摆烂": "懈怠",
}


# ---- 敏感词等级映射 ----
_BLOCKED_WORDS = set(_POLITICAL_WORDS + _EXPLICIT_WORDS + _ADVERTISING_WORDS)
_WARNED_WORDS = set(_VIOLENCE_WORDS)
_REPLACED_WORDS = set(_MODERN_SLANG_WORDS)


def _build_regex(words: set[str]) -> re.Pattern:
    """构建正则表达式（按词长降序，避免短词先匹配）。"""
    if not words:
        return re.compile(r"$^")  # 永不匹配
    sorted_words = sorted(words, key=len, reverse=True)
    # 转义特殊字符
    pattern = "|".join(re.escape(w) for w in sorted_words)
    return re.compile(pattern)


_BLOCKED_REGEX = _build_regex(_BLOCKED_WORDS)
_WARNED_REGEX = _build_regex(_WARNED_WORDS)
_REPLACED_REGEX = _build_regex(_REPLACED_WORDS)


# ---- 过滤结果 ----

class FilterResult:
    """内容过滤结果。"""

    def __init__(
        self,
        *,
        is_blocked: bool = False,
        is_warned: bool = False,
        has_replacement: bool = False,
        blocked_words: list[str] | None = None,
        warned_words: list[str] | None = None,
        replaced_pairs: list[tuple[str, str]] | None = None,
        cleaned_text: str = "",
    ) -> None:
        self.is_blocked = is_blocked
        self.is_warned = is_warned
        self.has_replacement = has_replacement
        self.blocked_words = blocked_words or []
        self.warned_words = warned_words or []
        self.replaced_pairs = replaced_pairs or []
        self.cleaned_text = cleaned_text

    def has_issue(self) -> bool:
        """是否有任何问题（blocked / warned / replaced）。"""
        return self.is_blocked or self.is_warned or self.has_replacement

    def to_dict(self) -> dict[str, Any]:
        """转 dict（日志/调试用）。"""
        return {
            "is_blocked": self.is_blocked,
            "is_warned": self.is_warned,
            "has_replacement": self.has_replacement,
            "blocked_words": self.blocked_words,
            "warned_words": self.warned_words,
            "replaced_pairs": self.replaced_pairs,
            "cleaned_text": self.cleaned_text,
        }


def filter_text(text: str) -> FilterResult:
    """过滤文本：检测敏感词 + 替换现代网络用语。

    Args:
        text: 待过滤的文本（玩家输入或 LLM 输出）

    Returns:
        FilterResult：包含检测结果和清洗后的文本
    """
    if not text:
        return FilterResult(cleaned_text=text)

    # 1. 检测 blocked 词（政治/色情/广告）
    blocked_matches = _BLOCKED_REGEX.findall(text)
    is_blocked = bool(blocked_matches)

    # 2. 检测 warned 词（暴力）
    warned_matches = _WARNED_REGEX.findall(text)
    is_warned = bool(warned_matches)

    # 3. 替换 modern_slang 词
    cleaned = text
    replaced_pairs: list[tuple[str, str]] = []

    def _replace_match(m: re.Match) -> str:
        original = m.group(0)
        replacement = _REPLACEMENT_MAP.get(original, original)
        if replacement != original:
            replaced_pairs.append((original, replacement))
        return replacement

    cleaned = _REPLACED_REGEX.sub(_replace_match, cleaned)

    result = FilterResult(
        is_blocked=is_blocked,
        is_warned=is_warned,
        has_replacement=bool(replaced_pairs),
        blocked_words=blocked_matches,
        warned_words=warned_matches,
        replaced_pairs=replaced_pairs,
        cleaned_text=cleaned,
    )

    if is_blocked:
        logger.warning(
            "内容安全过滤：检测到 blocked 词 %s，将触发降级",
            blocked_matches,
        )
    if is_warned:
        logger.info(
            "内容安全过滤：检测到 warned 词 %s",
            warned_matches,
        )
    if replaced_pairs:
        logger.info(
            "内容安全过滤：替换了 %d 个 modern_slang 词",
            len(replaced_pairs),
        )

    return result


def should_degrade_for_blocked(filter_result: FilterResult) -> bool:
    """判断是否应因敏感词触发降级。

    策略：
    - blocked 词命中：必须降级（不展示原始内容给玩家）
    - warned 词命中：不降级，但记录日志
    - modern_slang 替换：不降级，返回清洗后的文本
    """
    return filter_result.is_blocked


def sanitize_llm_output(text: str) -> tuple[str, FilterResult]:
    """清洗 LLM 输出。

    Args:
        text: LLM 原始输出

    Returns:
        (cleaned_text, filter_result)
        - 如果命中 blocked 词，cleaned_text 为空字符串（触发降级）
        - 如果命中 modern_slang，cleaned_text 为替换后的文本
        - 否则 cleaned_text 与原文本一致
    """
    result = filter_text(text)
    if should_degrade_for_blocked(result):
        return "", result
    return result.cleaned_text, result


if __name__ == "__main__":
    # 自测
    print("=== 内容安全过滤自测 ===\n")

    test_cases = [
        ("正常的修仙叙事文本", "应无任何问题"),
        ("他说666，大佬真厉害", "应替换 modern_slang"),
        ("我要用支付宝转账", "应替换 modern_slang（支付宝→灵石）"),
        ("天安门事件你知道吗", "应 blocked（政治敏感）"),
        ("你这家伙真是个傻逼", "应 blocked（色情低俗）"),
        ("加微信免费领取", "应 blocked（广告引流）"),
        ("弟子近日emo了，想躺平", "应替换（emo→心魔, 躺平→闭关）"),
    ]

    for text, desc in test_cases:
        result = filter_text(text)
        print(f"输入: {text}")
        print(f"期望: {desc}")
        print(f"结果: blocked={result.is_blocked}, warned={result.is_warned}, replaced={result.has_replacement}")
        if result.blocked_words:
            print(f"  blocked: {result.blocked_words}")
        if result.warned_words:
            print(f"  warned: {result.warned_words}")
        if result.replaced_pairs:
            print(f"  replaced: {result.replaced_pairs}")
        print(f"  cleaned: {result.cleaned_text}")
        print()
