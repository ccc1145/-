"""自由输入处理器：理解玩家自由输入意图，生成回应。

策划书 3.2.2 节定义流程：
    Step 1: 理解意图（classify_intent）
            → "询问" / "请求" / "闲聊" / "挑衅" / "无关"
    Step 2: 映射到游戏动作（map_to_action）
            → "询问修炼方法"：master.affinity +2
            → "挑衅"：master.affinity -10
    Step 3: 生成叙事回应

Day 8 实现：
- 意图分类（双通道：关键词快速分类 + LLM 精细分类）
- OOC 检测（玩家输入超出修仙世界观时的提示）
- 回应生成 Prompt 构建

注意：意图到游戏动作的映射规则由后端维护（策划书 741 行），
本模块只负责分类和回应生成，不做状态变更。
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from prompt_builder import PromptBuilder

if TYPE_CHECKING:
    # 仅用于类型注解，运行时不导入（避免 ai_agent_framework 依赖）
    from llm_adapter import NarrativeLLMAdapter


# 意图类型枚举（对齐策划书 3.2.2 Step 1）
INTENT_ASK = "ask"           # 询问（修炼、世界观、NPC 信息等）
INTENT_REQUEST = "request"   # 请求（拜师、要物品、求指点）
INTENT_CHAT = "chat"          # 闲聊（天气、心情、家常）
INTENT_PROVOKE = "provoke"   # 挑衅（不敬、挑战、嘲讽）
INTENT_IRRELEVANT = "irrelevant"  # 无关（现代话题、出戏内容）

# 关键词映射表（用于离线快速分类，零延迟）
# 顺序很重要：挑衅 > 闲聊（天气等强信号） > 请求 > 询问（避免"师父"误判）
_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    (INTENT_PROVOKE, [
        "挑战", "比试", "打一场", "你不配", "算什么", "废物", "无能",
        "嘲讽", "讽刺", "哼", "切", "不过如此", "瞧不起", "鄙视",
        "我要打你", "不服", "造反", "背叛",
    ]),
    # 闲聊优先于询问：天气/心情/问候等强信号先判
    (INTENT_CHAT, [
        "天气", "今日", "心情", "感觉", "觉得", "吃饭", "累",
        "好看", "漂亮", "辛苦", "早安", "晚安", "谢谢", "感谢",
        "告辞", "再见", "心情可好", "身体可好",
    ]),
    (INTENT_REQUEST, [
        "拜师", "收我为徒", "请教", "求", "赐", "赐教", "传授",
        "给我", "能给我", "想要", "希望", "恳请", "请师父",
        "想学", "想修炼", "带我", "指点我",
    ]),
    (INTENT_ASK, [
        "为什么", "怎么", "如何", "什么是", "是什么", "为何",
        "请问", "敢问", "何为", "何故", "哪里", "何时", "何人",
        "灵根", "修为", "境界", "功法", "炼丹", "炼器",
        "门派", "宗门", "青云门",
        # 注意：不单独用"师父"/"师兄"，避免闲聊误判
        "什么", "哪", "谁", "多少",
    ]),
]


class FreeInputProcessor:
    """自由输入处理器：意图分类 + OOC 检测 + 回应生成 Prompt 构建。

    用法：
        processor = FreeInputProcessor(llm_adapter, prompt_builder)
        # Step 1: 意图分类（离线快速版）
        intent = processor.classify_intent_offline("师父，弟子想请教修炼之法")
        # Step 1: 意图分类（LLM 精细版，可选）
        intent = processor.classify_intent_llm("弟子想请教修炼之法", npc_name="玄清真人")
        # Step 2: OOC 检测
        is_ooc, reason = processor.detect_ooc("我要玩手机")
        # Step 3: 构建回应生成 Prompt
        user_prompt = processor.build_response_prompt(...)
    """

    def __init__(
        self,
        llm_adapter: NarrativeLLMAdapter | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._llm = llm_adapter
        self._prompt_builder = prompt_builder or PromptBuilder()

    # ---- Step 1: 意图分类 ----

    def classify_intent_offline(self, text: str) -> dict[str, Any]:
        """离线关键词意图分类（零延迟，用于快速兜底）。

        Returns:
            {"intent": "ask|request|chat|provoke|irrelevant",
             "confidence": float, "matched_keywords": list[str], "method": "keyword"}
        """
        text_lower = text.lower()
        for intent, keywords in _KEYWORD_RULES:
            matched = [kw for kw in keywords if kw in text_lower]
            if matched:
                # 置信度：匹配关键词数 / 文本长度的对数衰减
                confidence = min(0.95, 0.5 + len(matched) * 0.15)
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "matched_keywords": matched,
                    "method": "keyword",
                }
        # 无匹配
        return {
            "intent": INTENT_IRRELEVANT,
            "confidence": 0.3,
            "matched_keywords": [],
            "method": "keyword",
        }

    def classify_intent_llm(
        self, text: str, npc_name: str = "", scene_name: str = ""
    ) -> dict[str, Any]:
        """LLM 精细意图分类（更准确，但有 LLM 调用延迟）。

        Returns:
            {"intent": "ask|request|chat|provoke|irrelevant",
             "target": "NPC名", "topic": "主题", "confidence": float, "method": "llm"}
        """
        if not self._llm:
            # 无 LLM 时退化为离线分类
            return self.classify_intent_offline(text)

        system_prompt = (
            "你是修仙游戏中的意图分类器。根据玩家的自由输入，判断其意图类别。\n\n"
            "意图类别：\n"
            "- ask: 询问修炼、世界观、NPC 信息等\n"
            "- request: 请求（拜师、要物品、求指点）\n"
            "- chat: 闲聊（天气、心情、家常）\n"
            "- provoke: 挑衅（不敬、挑战、嘲讽）\n"
            "- irrelevant: 无关（现代话题、出戏内容）\n\n"
            "输出严格 JSON，不要附加文字：\n"
            '{"intent": "类别", "target": "目标NPC名或空", "topic": "主题简述", "confidence": 0.0-1.0}'
        )
        user_prompt = f"玩家输入：{text}\n当前场景：{scene_name}\n在场NPC：{npc_name}"

        try:
            raw = self._llm.generate(system_prompt, user_prompt)
            # 复用 parser 的 JSON 提取逻辑
            parsed = self._extract_json(raw)
            if parsed and "intent" in parsed:
                parsed["method"] = "llm"
                # 校验 intent 值合法
                valid_intents = {
                    INTENT_ASK, INTENT_REQUEST, INTENT_CHAT,
                    INTENT_PROVOKE, INTENT_IRRELEVANT,
                }
                if parsed["intent"] not in valid_intents:
                    parsed["intent"] = INTENT_IRRELEVANT
                parsed.setdefault("confidence", 0.7)
                parsed.setdefault("target", "")
                parsed.setdefault("topic", "")
                return parsed
        except Exception:
            pass

        # LLM 失败退化为离线分类
        return self.classify_intent_offline(text)

    # ---- Step 2: OOC 检测 ----

    # OOC（Out of Character）关键词：玩家说出修仙世界不存在的事物
    _OOC_KEYWORDS = [
        # 现代科技
        "手机", "电脑", "网络", "wifi", "互联网", "电视", "电影",
        "游戏", "app", "微信", "QQ", "抖音", "快手", "B站", "bilibili",
        "外卖", "快递", "高铁", "飞机", "汽车", "公交车",
        # 现代概念
        "学校", "考试", "作业", "数学", "物理", "化学",
        "上班", "下班", "加班", "工资", "支付宝", "银行卡",
        "疫情", "核酸", "口罩",
        # 网络用语（出戏）
        "666", "yyds", "emo", "卷王", "摆烂", "躺平", "破防",
        "种草", "拔草", "带货", "直播",
    ]

    def detect_ooc(self, text: str) -> tuple[bool, str]:
        """检测玩家输入是否 OOC（超出修仙世界观）。

        Returns:
            (is_ooc: bool, reason: str)
            reason 为 OOC 原因说明，非 OOC 时为空字符串
        """
        text_lower = text.lower()
        for kw in self._OOC_KEYWORDS:
            if kw in text_lower:
                return True, f"检测到出戏词汇：{kw}"
        return False, ""

    # ---- Step 3: 回应生成 Prompt 构建 ----

    def build_response_prompt(
        self,
        *,
        player_input: str,
        intent: dict[str, Any],
        game_state: dict[str, Any],
        current_scene: dict[str, Any],
        npc_cards: dict[str, Any],
        memory: dict[str, Any],
        is_ooc: bool = False,
        ooc_reason: str = "",
    ) -> str:
        """构建自由输入回应的 user_prompt（交给 LLM 生成叙事）。

        system_prompt 复用 PromptBuilder.build_system_prompt。
        """
        return self._prompt_builder.build_free_input_response_prompt(
            player_input=player_input,
            intent=intent,
            game_state=game_state,
            current_scene=current_scene,
            npc_cards=npc_cards,
            memory=memory,
            is_ooc=is_ooc,
            ooc_reason=ooc_reason,
        )

    # ---- 辅助：JSON 提取 ----

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """从 LLM 输出中提取 JSON（复用 parser 的 3 策略简化版）。"""
        # 直接解析
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # Markdown 代码块
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError):
                pass
        # 花括号提取
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass
        return None


if __name__ == "__main__":
    # 自测：离线意图分类
    processor = FreeInputProcessor()

    test_cases = [
        ("师父，弟子想请教修炼之法", "request"),
        ("你这老东西算什么东西", "provoke"),
        ("什么是灵根", "ask"),
        ("今日天气不错", "chat"),
        ("我要玩手机", "irrelevant"),
    ]

    print("=== 离线意图分类自测 ===")
    for text, expected in test_cases:
        result = processor.classify_intent_offline(text)
        status = "✓" if result["intent"] == expected else "✗"
        print(f"{status} [{result['intent']}] {text}")
        print(f"  匹配词: {result['matched_keywords']}, 置信度: {result['confidence']}")

    print("\n=== OOC 检测自测 ===")
    ooc_cases = [
        "师父，我想玩手机",
        "弟子该如何修炼",
        "这游戏卡顿了",
        "敢问何为灵根",
    ]
    for text in ooc_cases:
        is_ooc, reason = processor.detect_ooc(text)
        tag = "[OOC]" if is_ooc else "[正常]"
        print(f"{tag} {text} → {reason}")
