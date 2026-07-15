"""Day 5 端到端测试：验证 NarrativeController 完整流程。

运行方式：
    cd d:\\实训\\xiuxian-simulator

    # 离线测试（FakeLLM，无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day5.py

    # 真实 MiMo 测试（需 API Key）
    $env:MIMO_API_KEY="sk-xxx"
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day5.py --real
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---- 开发期 path 处理 ----
AGENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_ROOT.parent
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"
sys.path.insert(0, str(FRAMEWORK_SRC))
sys.path.insert(0, str(AGENT_ROOT / "src"))

from ai_agent_framework.config.settings import LLMConfig  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from narrative_controller import NarrativeController  # noqa: E402


# ---- Mock 数据 ----
MOCK_GAME_STATE = {
    "player": {
        "name": "李逍遥",
        "cultivation": 10,
        "realm": {"major": "练气", "minor": 1},
        "spirit_root": {"type": "火", "quality": 7},
        "attributes": {"strength": 5, "agility": 6, "intelligence": 7, "perception": 6},
    }
}

MOCK_SCENE = {
    "id": "trial_grounds",
    "name": "试炼场",
    "description": "试炼场中央立着一块古朴的测灵石，四周环绕着淡淡的灵气。",
    "mood": "庄严、期待",
}

MOCK_NPC_CARDS = {
    "master": {
        "id": "master",
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

MOCK_PLAYER_INPUT_CHOICE = {"type": "choice", "value": "touch_stone", "choice_text": "触摸测灵石"}
MOCK_PLAYER_INPUT_FREE = {"type": "free_input", "text": "弟子想请教修炼之法"}

MOCK_EVENT_CONTEXT = {
    "event_id": "entrance_trial",
    "triggered_effects": [
        {"type": "modify_attribute", "target": "player.cultivation", "value": 10}
    ],
}

MOCK_MEMORY = {"recent_events": [], "dialogue_history": {}}


def _build_llm_config(use_real: bool) -> LLMConfig:
    """构建 LLM 配置：离线用 fake，真实用 MiMo。"""
    if not use_real:
        return LLMConfig(provider="fake", model="fake")

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("[错误] 真实 LLM 模式需要环境变量 MIMO_API_KEY")
        sys.exit(1)

    return LLMConfig(
        provider="openai",
        model="mimo-v2.5",
        api_key=api_key,
        base_url="https://api.xiaomimimo.com/v1",
        temperature=0.8,
        # MiMo 是推理模型，思考+正文都需要配额
        max_tokens=4000,
    )


def test_offline_degradation():
    """测试 1：离线 FakeLLM 必然触发降级（FakeLLM 返回固定文本，无法解析为合法 JSON）。"""
    print("=" * 60)
    print("[测试 1] 离线 FakeLLM 降级机制验证")
    print("=" * 60)

    fake_config = LLMConfig(provider="fake", model="fake")
    adapter = NarrativeLLMAdapter(fake_config)
    controller = NarrativeController(adapter, max_retries=3, timeout=30.0)

    result = controller.generate_scene_narrative(
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        player_input=MOCK_PLAYER_INPUT_CHOICE,
        event_context=MOCK_EVENT_CONTEXT,
        memory=MOCK_MEMORY,
        npc_cards=MOCK_NPC_CARDS,
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"narrative: {result.get('narrative', '')[:60]}...")
    print(f"choices: {len(result.get('available_choices', []))} 个")
    print(f"thought: {result.get('thought', '')[:80]}...")

    # 断言：FakeLLM 必然降级
    assert result.get("degraded") is True, "FakeLLM 输出非合法 JSON，应触发降级"
    assert len(result["available_choices"]) >= 1, "降级响应必须有选项"
    assert "trial_grounds" in result.get("thought", ""), "降级 thought 应含 scene_id"

    print("\n[FakeLLM 降级] 所有断言通过 ✓\n")


def test_real_mimo_scene_narrative():
    """测试 2：真实 MiMo 场景叙事生成。"""
    print("=" * 60)
    print("[测试 2] 真实 MiMo 场景叙事生成")
    print("=" * 60)

    mimo_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(mimo_config)
    controller = NarrativeController(adapter, max_retries=3, timeout=60.0)

    result = controller.generate_scene_narrative(
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        player_input=MOCK_PLAYER_INPUT_CHOICE,
        event_context=MOCK_EVENT_CONTEXT,
        memory=MOCK_MEMORY,
        npc_cards=MOCK_NPC_CARDS,
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"narrative:\n{result.get('narrative', '')}")
    print(f"\nsegments: {len(result.get('narrative_segments', []))} 段")
    for i, seg in enumerate(result.get("narrative_segments", []), 1):
        speaker = seg.get("speaker", "旁白")
        print(f"  [{i}] {seg.get('type')} / {speaker}: {seg.get('text', '')[:40]}...")
    print(f"\navailable_choices:")
    for c in result.get("available_choices", []):
        print(f"  - {c.get('id')}: {c.get('text')}")
    print(f"\nthought: {result.get('thought', '')[:100]}...")

    # 断言
    assert not result.get("degraded"), f"MiMo 应正常返回，但降级了: {result.get('thought')}"
    assert result.get("narrative"), "narrative 不能为空"
    assert len(result.get("available_choices", [])) >= 1, "必须有选项"
    assert 1 <= len(result["available_choices"]) <= 4, "选项数 1-4 个"

    # 修仙感检查：narrative 不应含禁忌词
    forbidden = ["666", "牛掰", "大佬", "系统", "bug", "ok", "cool"]
    narrative_text = result.get("narrative", "")
    for word in forbidden:
        assert word not in narrative_text.lower(), f"narrative 含禁忌词: {word}"

    print("\n[MiMo 场景叙事] 所有断言通过 ✓\n")


def test_real_mimo_npc_dialogue():
    """测试 3：真实 MiMo NPC 对话生成。"""
    print("=" * 60)
    print("[测试 3] 真实 MiMo NPC 对话生成")
    print("=" * 60)

    mimo_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(mimo_config)
    controller = NarrativeController(adapter, max_retries=3, timeout=60.0)

    result = controller.generate_npc_dialogue(
        npc=MOCK_NPC_CARDS["master"],
        player_input=MOCK_PLAYER_INPUT_FREE,
        current_scene=MOCK_SCENE,
        dialogue_history=["玩家：拜见师父", "玄清真人：嗯，来了。"],
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"narrative: {result.get('narrative', '')}")
    if result.get("narrative_segments"):
        print(f"\nsegments:")
        for i, seg in enumerate(result.get("narrative_segments", []), 1):
            speaker = seg.get("speaker", "旁白")
            print(f"  [{i}] {seg.get('type')} / {speaker}: {seg.get('text', '')[:60]}...")
    print(f"\navailable_choices:")
    for c in result.get("available_choices", []):
        print(f"  - {c.get('id')}: {c.get('text')}")

    # 断言
    assert not result.get("degraded"), f"MiMo NPC 对话应正常返回: {result.get('thought')}"
    assert result.get("narrative"), "narrative 不能为空"

    print("\n[MiMo NPC 对话] 所有断言通过 ✓\n")


def test_real_mimo_free_input():
    """测试 4：真实 MiMo 自由输入回应（玩家自由输入文本）。"""
    print("=" * 60)
    print("[测试 4] 真实 MiMo 自由输入回应")
    print("=" * 60)

    mimo_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(mimo_config)
    controller = NarrativeController(adapter, max_retries=3, timeout=60.0)

    # 玩家自由输入：询问灵根
    free_input = {"type": "free_input", "text": "师父，弟子的灵根如何？适合修炼什么功法？"}

    result = controller.generate_scene_narrative(
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        player_input=free_input,
        event_context={"event_id": "free_input", "triggered_effects": []},
        memory=MOCK_MEMORY,
        npc_cards=MOCK_NPC_CARDS,
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"narrative:\n{result.get('narrative', '')}")
    print(f"\navailable_choices:")
    for c in result.get("available_choices", []):
        print(f"  - {c.get('id')}: {c.get('text')}")

    # 断言
    assert not result.get("degraded"), f"MiMo 自由输入应正常返回: {result.get('thought')}"
    assert result.get("narrative"), "narrative 不能为空"

    print("\n[MiMo 自由输入] 所有断言通过 ✓\n")


if __name__ == "__main__":
    use_real = "--real" in sys.argv

    # 测试 1：离线降级（始终运行）
    test_offline_degradation()

    if use_real:
        # 测试 2-4：真实 MiMo
        test_real_mimo_scene_narrative()
        test_real_mimo_npc_dialogue()
        test_real_mimo_free_input()

        print("=" * 60)
        print("Day 5 全部测试通过 ✓（含真实 MiMo 端到端）")
        print("交付物: world_knowledge.py / system_prompt.j2 优化 / narrative_controller.py")
        print("=" * 60)
    else:
        print("=" * 60)
        print("Day 5 离线测试通过 ✓")
        print("提示: 加 --real 参数运行真实 MiMo 端到端测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day5.py --real")
        print("=" * 60)
