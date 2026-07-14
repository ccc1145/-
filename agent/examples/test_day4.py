"""Day 4 综合测试：验证 prompt_builder / parser / memory 三件套协同工作。

运行方式：
    cd d:\\实训\\xiuxian-simulator
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day4.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---- 开发期 path 处理 ----
AGENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_ROOT.parent
sys.path.insert(0, str(AGENT_ROOT / "src"))

from memory import MemoryManager  # noqa: E402
from parser import AgentOutputParser  # noqa: E402
from prompt_builder import PromptBuilder  # noqa: E402


# ---- Mock 数据 ----
MOCK_WORLD_KNOWLEDGE = [
    "青云门建派三百年，是修仙界四大宗门之一",
    "测灵石用于检测灵根属性，由上古修士遗留",
    "练气期共九层，筑基期方可正式踏入修仙之门",
]

MOCK_SCENE = {
    "id": "trial_grounds",
    "name": "试炼场",
    "description": "试炼场中央立着一块古朴的测灵石，四周环绕着淡淡的灵气。",
    "mood": "庄严、期待",
}

MOCK_NPC_CARDS = {
    "master": {
        "name": "玄清真人",
        "personality": {
            "traits": ["严厉", "护短"],
            "values": ["门派荣誉", "弟子心性"],
            "dislikes": ["浮夸", "不敬师长"],
            "speaking_style": "言简意赅，偶尔带文言",
        },
        "current_affinity": 5,
    }
}

MOCK_GAME_STATE = {
    "player": {
        "name": "李逍遥",
        "cultivation": 10,
        "realm": {"major": "练气", "minor": 1},
        "spirit_root": {"type": "火", "quality": 7},
    }
}

MOCK_PLAYER_INPUT_CHOICE = {"type": "choice", "value": "touch_stone", "choice_text": "触摸测灵石"}
MOCK_PLAYER_INPUT_FREE = {"type": "free_input", "text": "弟子想请教修炼之法"}

MOCK_EVENT_CONTEXT = {
    "event_id": "entrance_trial",
    "triggered_effects": [
        {"type": "modify_attribute", "target": "player.cultivation", "value": 10}
    ],
}


def test_prompt_builder_full():
    """测试 PromptBuilder 的三个 build 方法。"""
    print("=" * 60)
    print("[测试 1] PromptBuilder 完整渲染")
    print("=" * 60)

    builder = PromptBuilder()

    # 1. system_prompt
    system_prompt = builder.build_system_prompt(
        world_knowledge=MOCK_WORLD_KNOWLEDGE,
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
    )
    print("\n--- system_prompt (前 200 字) ---")
    print(system_prompt[:200] + "...")
    assert "玄清真人" in system_prompt, "system_prompt 应包含 NPC 名"
    assert "试炼场" in system_prompt, "system_prompt 应包含场景名"

    # 2. scene_narrative_prompt
    scene_prompt = builder.build_scene_narrative_prompt(
        game_state=MOCK_GAME_STATE,
        player_input=MOCK_PLAYER_INPUT_CHOICE,
        event_context=MOCK_EVENT_CONTEXT,
        memory={"recent_events": [], "dialogue_history": {}},
    )
    print("\n--- scene_narrative_prompt (前 300 字) ---")
    print(scene_prompt[:300] + "...")
    assert "李逍遥" in scene_prompt, "scene_prompt 应包含玩家名"
    assert "触摸测灵石" in scene_prompt, "scene_prompt 应包含玩家选择"

    # 3. npc_dialogue_prompt
    npc_prompt = builder.build_npc_dialogue_prompt(
        npc=MOCK_NPC_CARDS["master"],
        player_input=MOCK_PLAYER_INPUT_FREE,
        current_scene=MOCK_SCENE,
        dialogue_history=["玩家：拜见师父", "玄清真人：嗯，来了。"],
    )
    print("\n--- npc_dialogue_prompt (完整) ---")
    print(npc_prompt)
    assert "玄清真人" in npc_prompt, "npc_dialogue_prompt 应包含 NPC 名"
    assert "严厉" in npc_prompt, "npc_dialogue_prompt 应包含性格"
    assert "友善" in npc_prompt, "好感度 5 应判定为友善"

    print("\n[PromptBuilder] 所有断言通过 ✓\n")


def test_parser_with_realistic_llm_output():
    """测试 Parser 解析模拟的 LLM 输出。"""
    print("=" * 60)
    print("[测试 2] Parser 解析模拟 LLM 输出")
    print("=" * 60)

    parser = AgentOutputParser()

    # 模拟 MiMo 真实返回的 JSON（带 ```json 代码块）
    realistic_output = """```json
{
  "narrative": "你将手放在测灵石上，一股温热的气息顺着手臂流入体内。测灵石表面浮现出赤红色的纹路，光芒越来越盛。",
  "narrative_segments": [
    {"type": "narration", "text": "你将手放在测灵石上，一股温热的气息顺着手臂流入体内。"},
    {"type": "dialogue", "speaker": "玄清真人", "text": "嗯，火灵根，品质七等。尚可。"}
  ],
  "available_choices": [
    {"id": "express_gratitude", "text": "弟子拜谢长老"},
    {"id": "stay_silent", "text": "默默退到一旁"},
    {"id": "ask_question", "text": "询问修炼之法"}
  ]
}
```"""

    result = parser.parse(realistic_output)
    print(f"\n解析结果: parse_failed={result.get('parse_failed', False)}")
    print(f"  narrative: {result.get('narrative', '')[:50]}...")
    print(f"  segments: {len(result.get('narrative_segments', []))} 段")
    print(f"  choices: {len(result.get('available_choices', []))} 个")

    assert not result.get("parse_failed"), "应解析成功"
    assert len(result["available_choices"]) == 3, "应有 3 个选项"
    assert result["narrative_segments"][1]["speaker"] == "玄清真人", "第 2 段 speaker 应为玄清真人"

    print("\n[Parser] 所有断言通过 ✓\n")


def test_memory_manager():
    """测试 MemoryManager 的记忆管理。"""
    print("=" * 60)
    print("[测试 3] MemoryManager 记忆管理")
    print("=" * 60)

    manager = MemoryManager(max_turns=3, npc_max_history=3)

    # 模拟 3 轮游戏
    for i in range(1, 4):
        manager.add_turn(
            turn=i,
            player_input=f"操作{i}",
            narrative=f"第{i}轮叙事内容",
        )

    # 模拟 NPC 对话
    manager.add_npc_dialogue("master", "拜见师父", "嗯，来了。")
    manager.add_npc_dialogue("master", "请教修炼", "心要静。")

    ctx = manager.get_prompt_context()
    print(f"\nrecent_events: {len(ctx['recent_events'])} 条")
    print(f"dialogue_history NPC 数: {len(ctx['dialogue_history'])}")
    print(f"master 对话轮数: {len(ctx['dialogue_history']['master'])}")

    assert len(ctx["recent_events"]) == 3, "应有 3 条短期记忆"
    assert "master" in ctx["dialogue_history"], "应有 master 的对话历史"
    assert len(ctx["dialogue_history"]["master"]) == 2, "master 应有 2 轮对话"

    # 测试窗口裁剪
    manager.add_turn(turn=4, player_input="操作4", narrative="第4轮")
    ctx = manager.get_prompt_context()
    assert len(ctx["recent_events"]) == 3, "窗口应裁剪到 3 条"
    assert ctx["recent_events"][0]["turn"] == 2, "最早应为第 2 轮"

    print("\n[MemoryManager] 所有断言通过 ✓\n")


def test_parser_success_rate():
    """测试 Parser 成功率（策划书要求 >90%）。"""
    print("=" * 60)
    print("[测试 4] Parser 成功率验证（目标 >90%）")
    print("=" * 60)

    parser = AgentOutputParser()

    # 20 个测试用例（覆盖各种 LLM 输出形态）
    cases = [
        # 标准格式（10 个）
        ('{"narrative":"a","available_choices":[{"id":"1","text":"x"}]}', True),
        ('{"narrative":"b","narrative_segments":[{"type":"narration","text":"b"}],"available_choices":[{"id":"2","text":"y"}]}', True),
        ('{"narrative":"c","available_choices":[{"id":"3","text":"z"},{"id":"4","text":"w"}]}', True),
        ('{"narrative":"d","available_choices":[{"id":"5","text":"v"}],"thought":"test"}', True),
        ('{"narrative":"e","available_choices":[{"id":"6","text":"u"}],"free_input_enabled":true}', True),
        ('{"narrative":"f","available_choices":[{"id":"7","text":"t"}],"state_changes":{"a":1}}', True),
        ('{"narrative":"g","available_choices":[{"id":"8","text":"s"}],"npc_reactions":{}}', True),
        ('{"narrative":"h","available_choices":[{"id":"9","text":"r"}],"next_scene_id":"x"}', True),
        ('{"narrative":"i","available_choices":[{"id":"10","text":"q"}]}', True),
        ('{"narrative":"j","available_choices":[{"id":"11","text":"p"}]}', True),
        # Markdown 代码块（5 个）
        ('```json\n{"narrative":"k","available_choices":[{"id":"12","text":"o"}]}\n```', True),
        ('```\n{"narrative":"l","available_choices":[{"id":"13","text":"n"}]}\n```', True),
        ('好的，这是叙事：\n```json\n{"narrative":"m","available_choices":[{"id":"14","text":"m"}]}\n```\n以上。', True),
        ('说明文字\n{"narrative":"n","available_choices":[{"id":"15","text":"l"}]}\n结尾', True),
        ('前缀{"narrative":"o","available_choices":[{"id":"16","text":"k"}]}后缀', True),
        # 边界情况（5 个）
        ('{"narrative":"p","available_choices":[{"id":"17","text":"j"},{"id":"18","text":"i"},{"id":"19","text":"h"},{"id":"20","text":"g"},{"id":"21","text":"f"}]}', True),  # 超 4 个会被截断
        ('{"narrative":"q","narrative_segments":[{"type":"dialogue","speaker":"x","text":"y"}],"available_choices":[{"id":"22","text":"e"}]}', True),
        ('{"narrative":"r","narrative_segments":[{"type":"narration","text":"r"}],"available_choices":[{"id":"23","text":"d"}]}', True),
        ('{"narrative":"s","available_choices":[{"id":"24","text":"c"}]}', True),
        ('{"narrative":"t","available_choices":[{"id":"25","text":"b"}]}', True),
    ]

    success = 0
    for raw, expected_success in cases:
        result = parser.parse(raw)
        ok = not result.get("parse_failed", False)
        if ok == expected_success:
            success += 1
        else:
            print(f"  [失败] 输入: {raw[:50]}... 期望: {expected_success} 实际: {ok}")

    rate = success / len(cases) * 100
    print(f"\n成功率: {success}/{len(cases)} = {rate:.1f}%")
    assert rate >= 90, f"Parser 成功率 {rate:.1f}% 低于 90% 要求"

    print(f"\n[Parser 成功率] {rate:.1f}% >= 90% ✓\n")


if __name__ == "__main__":
    test_prompt_builder_full()
    test_parser_with_realistic_llm_output()
    test_memory_manager()
    test_parser_success_rate()

    print("=" * 60)
    print("Day 4 全部测试通过 ✓")
    print("交付物: parser.py / memory.py / prompt_builder.py (升级) / npc_dialogue.j2")
    print("=" * 60)
