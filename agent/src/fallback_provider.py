"""Agent 输出降级预设文案提供器（Day 12）。

策划书 Day 12 任务 1：实现 Agent 输出降级（LLM 失败时 3 秒内返回预设文案）。

设计：
- 按 scene_id + request_type 提供完整的降级响应（含 narrative / segments / choices）
- 支持从 content/scenes/ 动态加载场景级预设（MVP 阶段先硬编码）
- 模板变量：{player_name} / {npc_name} / {scene_name} 动态填充
- 三类 request_type：scene_narrative / npc_dialogue / free_input

对齐文档：
- 策划书 5.4 节 _degraded_response
- docs/agent-io-format.md 第 5.2 节 降级响应结构
"""
from __future__ import annotations

from typing import Any


# 场景级预设文案（按 scene_id 索引）
# 每个场景提供 scene_narrative 和 npc_dialogue 两类降级文案
_SCENE_PRESETS: dict[str, dict[str, str]] = {
    "trial_grounds": {
        "scene_narrative": "你站在试炼场中央，面前的测灵石古朴沧桑，仿佛在等待你的触碰。周围的师兄师姐投来或期待或审视的目光。",
        "npc_dialogue": "玄清真人抚须不语，目光在测灵石上来回扫视，似在等待你的下一步动作。",
    },
    "trial_result": {
        "scene_narrative": "测灵石的光芒渐渐消散，你的灵根属性已明。无论结果如何，修仙之路才刚刚开始。",
        "npc_dialogue": "玄清真人微微颔首，似乎对你的表现有所评价，但并未开口。",
    },
    "sect_entrance": {
        "scene_narrative": "你踏入青云门的山门，迎面而来的是古朴的青石长阶，两侧松柏苍翠，灵气沁人心脾。",
        "npc_dialogue": "守门弟子看了你一眼，点头示意你进入。",
    },
    "cheng_yun_dian": {
        "scene_narrative": "承运殿内檀香袅袅，徐伯潜手持竹简，正端坐于案前讲学。",
        "npc_dialogue": "徐伯潜手中的竹简轻叩案几，抬眼看你，似在等待你开口。",
    },
    "default": {
        "scene_narrative": "你继续前行，前路漫漫，修仙之道在乎一心。",
        "npc_dialogue": "对方沉默片刻，未置一词。",
    },
}


# 自由输入降级文案（按 intent 索引）
_FREE_INPUT_PRESETS: dict[str, str] = {
    "ask": "你的疑问暂无人能解，或许日后再问不迟。",
    "request": "你的请求似乎未被理会，对方只是淡淡看了你一眼。",
    "chat": "你闲聊了几句，对方只是微微点头，未有多言。",
    "provoke": "你的话似乎引起了对方的注意，但对方并未接茬。",
    "irrelevant": "你的话似乎无人应答，唯有山风拂过。",
}


# 默认选项（降级时使用）
_DEFAULT_CHOICES = [
    {"id": "continue", "text": "继续前行"},
    {"id": "observe", "text": "环顾四周"},
]

_DEFAULT_DIALOGUE_CHOICES = [
    {"id": "continue", "text": "继续对话"},
    {"id": "take_leave", "text": "告退"},
]


def get_scene_preset(scene_id: str, request_type: str = "scene_narrative") -> str:
    """获取场景级预设文案。

    Args:
        scene_id: 场景 ID
        request_type: "scene_narrative" / "npc_dialogue"
    """
    scene = _SCENE_PRESETS.get(scene_id, _SCENE_PRESETS["default"])
    return scene.get(request_type, scene["scene_narrative"])


def get_free_input_preset(intent: str) -> str:
    """获取自由输入降级文案。"""
    return _FREE_INPUT_PRESETS.get(intent, _FREE_INPUT_PRESETS["irrelevant"])


def build_scene_fallback(
    *,
    scene_id: str,
    player_name: str = "道友",
    error: str = "",
) -> dict[str, Any]:
    """构建场景叙事降级响应。

    Args:
        scene_id: 场景 ID
        player_name: 玩家名（用于模板替换）
        error: 降级原因（调试用，不展示给玩家）

    Returns:
        符合 docs/agent-io-format.md 的降级响应 dict
    """
    narrative = get_scene_preset(scene_id, "scene_narrative").replace(
        "{player_name}", player_name
    )
    return {
        "narrative": narrative,
        "narrative_segments": [{"type": "narration", "text": narrative}],
        "available_choices": _DEFAULT_CHOICES,
        "free_input_enabled": True,
        "thought": f"DEGRADED: scene narrative fallback, scene={scene_id}, error={error}",
        "degraded": True,
    }


def build_dialogue_fallback(
    *,
    scene_id: str,
    npc_name: str = "对方",
    error: str = "",
) -> dict[str, Any]:
    """构建 NPC 对话降级响应。

    Args:
        scene_id: 场景 ID（用于场景级文案匹配）
        npc_name: NPC 名（用于文案模板替换）
        error: 降级原因（调试用）
    """
    narrative = get_scene_preset(scene_id, "npc_dialogue").replace(
        "{npc_name}", npc_name
    )
    return {
        "narrative": narrative,
        "narrative_segments": [
            {"type": "narration", "text": narrative},
        ],
        "available_choices": _DEFAULT_DIALOGUE_CHOICES,
        "free_input_enabled": True,
        "thought": f"DEGRADED: npc dialogue fallback, scene={scene_id}, npc={npc_name}, error={error}",
        "degraded": True,
    }


def build_free_input_fallback(
    *,
    intent: str,
    scene_id: str,
    player_name: str = "道友",
    error: str = "",
) -> dict[str, Any]:
    """构建自由输入降级响应。

    Args:
        intent: 意图分类结果（ask/request/chat/provoke/irrelevant）
        scene_id: 场景 ID
        player_name: 玩家名
        error: 降级原因
    """
    narrative = get_free_input_preset(intent).replace("{player_name}", player_name)
    return {
        "narrative": narrative,
        "narrative_segments": [{"type": "narration", "text": narrative}],
        "available_choices": _DEFAULT_DIALOGUE_CHOICES,
        "free_input_enabled": True,
        "thought": f"DEGRADED: free input fallback, intent={intent}, scene={scene_id}, error={error}",
        "degraded": True,
    }


if __name__ == "__main__":
    # 自测
    print("=== 场景叙事降级 ===")
    for sid in ["trial_grounds", "cheng_yun_dian", "unknown_scene"]:
        r = build_scene_fallback(scene_id=sid, player_name="李逍遥", error="test")
        print(f"\n[{sid}]")
        print(f"  narrative: {r['narrative'][:60]}...")
        print(f"  choices: {len(r['available_choices'])} 个")
        print(f"  degraded: {r['degraded']}")

    print("\n=== NPC 对话降级 ===")
    r = build_dialogue_fallback(scene_id="cheng_yun_dian", npc_name="徐伯潜", error="test")
    print(f"  narrative: {r['narrative'][:60]}...")

    print("\n=== 自由输入降级 ===")
    for intent in ["ask", "provoke", "irrelevant"]:
        r = build_free_input_fallback(intent=intent, scene_id="default", error="test")
        print(f"  [{intent}] {r['narrative'][:50]}...")
