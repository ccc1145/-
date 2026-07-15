"""Agent Mock 输出：供后端 (agent_bridge.py) 在 Agent 未接入前调试用。

策划书 7.2.2 节定义。人员C 在 Day 3 提供，人员B 基于此集成 Agent 调用。

使用方式：
    from mock_agent import MOCK_AGENT_OUTPUT, get_mock_agent_output

    # 直接用预设输出
    response = MOCK_AGENT_OUTPUT

    # 或根据 request_type 返回不同 Mock（后续扩展）
    response = get_mock_agent_output(request_type="scene_narrative")

Mock 版本：v1.0 - based on agent-io-format.md Day3
"""
from __future__ import annotations

from typing import Any


# 场景叙事 Mock 输出（对齐 docs/agent-io-format.md v0.1）
MOCK_SCENE_NARRATIVE_OUTPUT: dict[str, Any] = {
    "narrative": "你将手放在测灵石上，一股温热的气息顺着手臂流入体内。测灵石表面浮现出赤红色的纹路，光芒越来越盛，最终化作一缕火光消散在空气中。玄清真人抚须而立，目光中闪过一丝不易察觉的满意。",
    "narrative_segments": [
        {
            "type": "narration",
            "text": "你将手放在测灵石上，一股温热的气息顺着手臂流入体内。"
        },
        {
            "type": "narration",
            "text": "测灵石表面浮现出赤红色的纹路，光芒越来越盛，最终化作一缕火光消散在空气中。"
        },
        {
            "type": "dialogue",
            "speaker": "玄清真人",
            "text": "嗯，火灵根，品质七等。尚可。"
        }
    ],
    "state_changes": {
        "player.cultivation": 10
    },
    "next_scene_id": "trial_result",
    "available_choices": [
        {"id": "express_gratitude", "text": "弟子拜谢长老"},
        {"id": "stay_silent", "text": "默默退到一旁"},
        {"id": "ask_question", "text": "询问修炼之法"}
    ],
    "free_input_enabled": True,
    "npc_reactions": {
        "master": {
            "visible_emotion": "满意",
            "internal_thought": "此子灵根尚可，但需观察心性"
        }
    },
    "thought": "玩家选择测灵石，触发入门试炼。火灵根品质七等，修为+10。"
}


# NPC 对话 Mock 输出（Day 4 启用）
MOCK_NPC_DIALOGUE_OUTPUT: dict[str, Any] = {
    "narrative": "玄清真人看了你一眼，缓缓开口。",
    "narrative_segments": [
        {"type": "narration", "text": "玄清真人看了你一眼，缓缓开口。"},
        {"type": "dialogue", "speaker": "玄清真人", "text": "修行之路，重在心性。你且说来。"}
    ],
    "available_choices": [
        {"id": "ask_cultivation", "text": "询问修炼之法"},
        {"id": "ask_sect", "text": "询问门派之事"},
        {"id": "take_leave", "text": "告退"}
    ],
    "free_input_enabled": True,
    "thought": "Mock NPC 对话输出"
}


# 自由输入回应 Mock 输出（Day 8 启用）
MOCK_FREE_INPUT_OUTPUT: dict[str, Any] = {
    "narrative": "你向玄清真人表达了想变强的决心。",
    "narrative_segments": [
        {"type": "narration", "text": "你向玄清真人表达了想变强的决心。"},
        {"type": "dialogue", "speaker": "玄清真人", "text": "心志可嘉。既入我门，当潜心修炼。"}
    ],
    "available_choices": [
        {"id": "start_cultivation", "text": "开始修炼"},
        {"id": "ask_more", "text": "继续请教"}
    ],
    "free_input_enabled": True,
    "thought": "Mock 自由输入回应"
}


# 默认 Mock 输出（向后兼容策划书 7.2.2 节示例）
MOCK_AGENT_OUTPUT = MOCK_SCENE_NARRATIVE_OUTPUT


def get_mock_agent_output(request_type: str = "scene_narrative") -> dict[str, Any]:
    """根据请求类型返回对应的 Mock 输出。

    Args:
        request_type: 请求类型，见 docs/agent-io-format.md 第 1 节
            - "scene_narrative"  场景叙事（默认）
            - "npc_dialogue"     NPC 对话
            - "free_input_response"  自由输入回应

    Returns:
        符合 Agent 输出格式的 Mock dict
    """
    mapping = {
        "scene_narrative": MOCK_SCENE_NARRATIVE_OUTPUT,
        "npc_dialogue": MOCK_NPC_DIALOGUE_OUTPUT,
        "free_input_response": MOCK_FREE_INPUT_OUTPUT,
    }
    return mapping.get(request_type, MOCK_SCENE_NARRATIVE_OUTPUT)


if __name__ == "__main__":
    # 自测：打印所有 Mock 输出
    import json

    print("=" * 60)
    print("Mock Agent 输出（对齐 agent-io-format.md v0.1）")
    print("=" * 60)
    for req_type in ("scene_narrative", "npc_dialogue", "free_input_response"):
        print(f"\n--- request_type: {req_type} ---")
        print(json.dumps(get_mock_agent_output(req_type), ensure_ascii=False, indent=2))
