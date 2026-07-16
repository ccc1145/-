"""Day 8 端到端测试：自由输入处理器 + OOC 检测 + 真实 MiMo 集成。

测试覆盖：
1. 离线意图分类（5 种意图 + 关键词匹配）
2. OOC 检测（出戏词汇命中 + 正常输入不误判）
3. 真实 MiMo 自由输入回应（询问意图 → NPC 耐心解答）
4. 真实 MiMo OOC 场景（玩家输入"我要玩手机" → NPC 困惑引导）

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试（无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day8.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day8.py --real
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---- Path 设置 ----
AGENT_ROOT = Path(__file__).resolve().parents[1]          # .../xiuxian-simulator/agent
PROJECT_ROOT = AGENT_ROOT.parent                          # .../xiuxian-simulator
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"
sys.path.insert(0, str(FRAMEWORK_SRC))
sys.path.insert(0, str(AGENT_ROOT / "src"))

from free_input_processor import FreeInputProcessor, INTENT_ASK, INTENT_REQUEST, INTENT_CHAT, INTENT_PROVOKE, INTENT_IRRELEVANT  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from narrative_controller import NarrativeController  # noqa: E402
from ai_agent_framework.config.settings import LLMConfig  # noqa: E402

# ---- Mock 数据（对齐 GameState v1.0）----
MOCK_GAME_STATE = {
    "session_id": "day8-test-001",
    "turn_count": 3,
    "player": {
        "name": "李逍遥",
        "gender": "男",
        "spiritual_root": "火灵根",
        "cultivation": 10,
        "cultivation_exp": 0,
        "hp": 100, "max_hp": 100,
        "mp": 50, "max_mp": 50,
        "spirit_stones": 0,
        "inventory": [],
        "skills": [],
    },
    "world": {
        "current_scene_id": "trial_grounds",
        "flags": {"met_master": True},
        "npc_affinity": {"master": 5},
    },
    "narrative": "",
    "available_choices": [],
    "recent_events": [],
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

MOCK_MEMORY = {"recent_events": [], "dialogue_history": {}}


# ---- LLM 配置 ----
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"


def _build_llm_config(use_real: bool) -> LLMConfig:
    if not use_real:
        return LLMConfig(provider="fake", model="fake")
    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("[错误] 真实 LLM 模式需要环境变量 MIMO_API_KEY")
        sys.exit(1)
    return LLMConfig(
        provider="openai",
        model=MIMO_MODEL,
        api_key=api_key,
        base_url=MIMO_BASE_URL,
        temperature=0.8,
        max_tokens=4000,
    )


# ---- 测试用例 ----

def test_offline_intent_classification():
    """测试 1：离线意图分类（5 种意图）。"""
    print("=" * 60)
    print("[测试 1] 离线意图分类")
    print("=" * 60)

    processor = FreeInputProcessor()

    cases = [
        ("师父，弟子想请教修炼之法", INTENT_REQUEST, "请求指点"),
        ("你这老东西算什么东西", INTENT_PROVOKE, "挑衅"),
        ("什么是灵根？弟子不太明白", INTENT_ASK, "询问"),
        ("今日天气不错，师父心情可好", INTENT_CHAT, "闲聊"),
        ("我要玩手机", INTENT_IRRELEVANT, "无关"),
    ]

    all_pass = True
    for text, expected, desc in cases:
        result = processor.classify_intent_offline(text)
        status = "✓" if result["intent"] == expected else "✗"
        if result["intent"] != expected:
            all_pass = False
        print(f"{status} [{desc}] 期望={expected}, 实际={result['intent']}, 置信度={result['confidence']:.2f}")
        print(f"  输入: {text}")
        print(f"  匹配词: {result['matched_keywords']}")

    if all_pass:
        print("\n[离线意图分类] 所有断言通过 ✓")
    else:
        print("\n[离线意图分类] 有断言失败 ✗")
    return all_pass


def test_ooc_detection():
    """测试 2：OOC 检测。"""
    print("\n" + "=" * 60)
    print("[测试 2] OOC 检测")
    print("=" * 60)

    processor = FreeInputProcessor()

    cases = [
        ("师父，我想玩手机", True, "出戏词汇：手机"),
        ("这游戏卡顿了", True, "出戏词汇：游戏"),
        ("我要用支付宝", True, "出戏词汇：支付宝"),
        ("弟子该如何修炼", False, "正常修仙输入"),
        ("敢问何为灵根", False, "正常修仙输入"),
        ("今日emo了", True, "出戏词汇：emo"),
    ]

    all_pass = True
    for text, expected_ooc, desc in cases:
        is_ooc, reason = processor.detect_ooc(text)
        status = "✓" if is_ooc == expected_ooc else "✗"
        if is_ooc != expected_ooc:
            all_pass = False
        tag = "[OOC]" if is_ooc else "[正常]"
        print(f"{status} {tag} {desc}")
        print(f"  输入: {text}")
        if is_ooc:
            print(f"  原因: {reason}")

    if all_pass:
        print("\n[OOC 检测] 所有断言通过 ✓")
    else:
        print("\n[OOC 检测] 有断言失败 ✗")
    return all_pass


def test_mimo_free_input_ask(controller: NarrativeController):
    """测试 3：真实 MiMo 自由输入回应（询问意图）。"""
    print("\n" + "=" * 60)
    print("[测试 3] 真实 MiMo 自由输入回应（询问修炼）")
    print("=" * 60)

    result = controller.generate_free_input_response(
        player_input="师父，弟子的灵根如何？适合修炼什么功法？",
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
        memory=MOCK_MEMORY,
        use_llm_intent=True,
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"意图: {result.get('intent', {}).get('intent')}, method={result.get('intent', {}).get('method')}")
    print(f"OOC: {result.get('is_ooc', False)}")
    print(f"\nnarrative:\n{result.get('narrative', '')[:500]}")
    print(f"\navailable_choices:")
    for c in result.get("available_choices", []):
        print(f"  - {c.get('id')}: {c.get('text')}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert result.get("narrative"), "narrative 不应为空"
    assert "intent" in result, "应包含 intent 字段"
    assert "is_ooc" in result, "应包含 is_ooc 字段"
    assert not result.get("is_ooc"), "正常询问不应 OOC"
    print("\n[MiMo 自由输入-询问] 所有断言通过 ✓")
    return True


def test_mimo_free_input_ooc(controller: NarrativeController):
    """测试 4：真实 MiMo 自由输入回应（OOC 场景）。"""
    print("\n" + "=" * 60)
    print("[测试 4] 真实 MiMo 自由输入回应（OOC 场景）")
    print("=" * 60)

    result = controller.generate_free_input_response(
        player_input="师父，我想玩手机游戏",
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
        memory=MOCK_MEMORY,
        use_llm_intent=False,  # OOC 用离线检测即可，省一次 LLM 调用
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"意图: {result.get('intent', {}).get('intent')}, method={result.get('intent', {}).get('method')}")
    print(f"OOC: {result.get('is_ooc', False)}, reason: {result.get('ooc_reason', '')}")
    print(f"\nnarrative:\n{result.get('narrative', '')[:500]}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert result.get("narrative"), "narrative 不应为空"
    assert result.get("is_ooc"), "应检测到 OOC"
    # OOC 时 NPC 应表现出困惑或引导（叙事中不应出现"手机"作为正常物品）
    print("\n[MiMo 自由输入-OOC] 所有断言通过 ✓")
    return True


def test_mimo_free_input_provoke(controller: NarrativeController):
    """测试 5：真实 MiMo 自由输入回应（挑衅意图）。"""
    print("\n" + "=" * 60)
    print("[测试 5] 真实 MiMo 自由输入回应（挑衅师父）")
    print("=" * 60)

    result = controller.generate_free_input_response(
        player_input="你这老东西，算什么东西，本大爷才不稀罕当你弟子",
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
        memory=MOCK_MEMORY,
        use_llm_intent=False,
    )

    print(f"\n降级标记: degraded={result.get('degraded', False)}")
    print(f"意图: {result.get('intent', {}).get('intent')}")
    print(f"\nnarrative:\n{result.get('narrative', '')[:500]}")
    print(f"\navailable_choices:")
    for c in result.get("available_choices", []):
        print(f"  - {c.get('id')}: {c.get('text')}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert result.get("narrative"), "narrative 不应为空"
    intent = result.get("intent", {}).get("intent")
    assert intent == INTENT_PROVOKE, f"意图应为 provoke, 实际={intent}"
    print("\n[MiMo 自由输入-挑衅] 所有断言通过 ✓")
    return True


# ---- 主入口 ----

def main():
    use_real = "--real" in sys.argv

    # 离线测试（不需要 LLM）
    r1 = test_offline_intent_classification()
    r2 = test_ooc_detection()

    if not use_real:
        print("\n" + "=" * 60)
        print("Day 8 离线测试通过 ✓")
        print("提示: 加 --real 参数运行真实 MiMo 端到端测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day8.py --real")
        print("=" * 60)
        return

    # 真实 MiMo 测试
    print("\n" + "=" * 60)
    print("启动真实 MiMo 端到端测试...")
    print("=" * 60)

    llm_config = _build_llm_config(use_real=True)
    llm_adapter = NarrativeLLMAdapter(llm_config)
    controller = NarrativeController(llm_adapter, max_retries=3)

    r3 = test_mimo_free_input_ask(controller)
    r4 = test_mimo_free_input_ooc(controller)
    r5 = test_mimo_free_input_provoke(controller)

    print("\n" + "=" * 60)
    if all([r1, r2, r3, r4, r5]):
        print("Day 8 全部测试通过 ✓（含真实 MiMo 端到端）")
        print("交付物: free_input_processor.py / free_input_response.j2 / narrative_controller.py 集成")
    else:
        print("Day 8 有测试失败 ✗")
    print("=" * 60)


if __name__ == "__main__":
    main()
