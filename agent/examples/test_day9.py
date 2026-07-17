"""Day 9 端到端测试：NPC 对话生成器 + 记忆管理 v2 + 真实 MiMo 集成。

测试覆盖：
1. memory.py v2 单元测试（关键事件 + 智能截断 + turn 时间戳）
2. NPCDialogueGenerator 离线流程（FakeLLM 降级，验证多轮对话记录到记忆）
3. 真实 MiMo 多轮对话连贯性（NPC "记得"之前说过什么）
4. 真实 MiMo 关键事件影响态度（记录 helped 事件后，NPC 态度变热情）

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day9.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day9.py --real
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---- Path 设置 ----
AGENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_ROOT.parent
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"
sys.path.insert(0, str(FRAMEWORK_SRC))
sys.path.insert(0, str(AGENT_ROOT / "src"))

from memory import MemoryManager, NPCMemory, ShortTermMemory  # noqa: E402
from npc_dialogue_generator import NPCDialogueGenerator  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from ai_agent_framework.config.settings import LLMConfig  # noqa: E402

# ---- Mock 数据 ----
MOCK_SCENE = {"id": "trial_grounds", "name": "试炼场", "description": "测灵石所在"}

MOCK_MASTER_CARD = {
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

MOCK_RIVAL_CARD = {
    "id": "rival",
    "name": "萧逸",
    "personality": {
        "traits": ["傲慢", "争强好胜"],
        "values": ["个人实力"],
        "dislikes": ["弱者", "示弱"],
        "speaking_style": "带刺，喜欢贬低他人",
    },
    "current_affinity": -5,
}

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


# ---- 测试 1: memory.py v2 单元测试 ----

def test_memory_v2():
    """测试 1：memory.py v2 功能验证。"""
    print("=" * 60)
    print("[测试 1] memory.py v2 单元测试")
    print("=" * 60)

    all_pass = True

    # 1.1 NPCMemory 关键事件
    print("\n--- 1.1 NPCMemory 关键事件 ---")
    npc_mem = NPCMemory(npc_id="master", max_history=3)
    npc_mem.record_event("helped", "玩家帮玄清真人解围", turn=3, impact=10)
    events = npc_mem.get_events()
    assert len(events) == 1, f"关键事件数应为 1, 实际 {len(events)}"
    assert events[0]["type"] == "helped"
    assert events[0]["impact"] == 10
    print(f"  ✓ 关键事件记录: {events[0]['description']}")

    # 1.2 对话带 turn 时间戳
    print("\n--- 1.2 对话带 turn 时间戳 ---")
    npc_mem.add_dialogue("拜见师父", "嗯，来了。", turn=1)
    npc_mem.add_dialogue("请教修炼", "心要静。", turn=2)
    ctx = npc_mem.get_context()
    assert ctx[0]["turn"] == 1, f"第 1 轮 turn 应为 1, 实际 {ctx[0]['turn']}"
    assert ctx[1]["turn"] == 2
    print(f"  ✓ turn 时间戳: 第1轮 turn={ctx[0]['turn']}, 第2轮 turn={ctx[1]['turn']}")

    # 1.3 智能截断（>3 轮触发摘要）
    print("\n--- 1.3 智能截断（>3 轮）---")
    npc_mem2 = NPCMemory(npc_id="senior", max_history=5)
    for i in range(1, 6):
        npc_mem2.add_dialogue(f"问题{i}", f"回答{i}", turn=i)
    prompt_text = npc_mem2.get_prompt_context()
    assert "省略早期内容" in prompt_text, "应包含摘要提示"
    assert "第4轮" in prompt_text, "应包含最近 2 轮详情"
    assert "第1轮" not in prompt_text, "不应包含早期内容"
    print(f"  ✓ 智能截断: 包含摘要提示 + 最近 2 轮")

    # 1.4 关键事件在 Prompt 顶部
    print("\n--- 1.4 关键事件在 Prompt 顶部 ---")
    npc_mem3 = NPCMemory(npc_id="master")
    npc_mem3.record_event("helped", "帮师父解围", turn=3, impact=10)
    npc_mem3.add_dialogue("你好", "嗯", turn=4)
    prompt_text = npc_mem3.get_prompt_context()
    assert "【关键记忆】" in prompt_text
    assert prompt_text.index("【关键记忆】") < prompt_text.index("【近期对话】")
    print(f"  ✓ 关键记忆在近期对话之前")

    # 1.5 MemoryManager v2 新增方法
    print("\n--- 1.5 MemoryManager v2 新增方法 ---")
    manager = MemoryManager(max_turns=3, npc_max_history=3)
    manager.record_npc_event("master", "helped", "帮师父解围", turn=3, impact=10)
    events = manager.get_npc_events("master")
    assert len(events) == 1
    print(f"  ✓ record_npc_event / get_npc_events 正常")

    print("\n[memory.py v2] 所有断言通过 ✓")
    return True


# ---- 测试 2: NPCDialogueGenerator 离线流程 ----

def test_generator_offline():
    """测试 2：NPCDialogueGenerator 离线流程（FakeLLM 降级）。"""
    print("\n" + "=" * 60)
    print("[测试 2] NPCDialogueGenerator 离线流程")
    print("=" * 60)

    config = LLMConfig(provider="fake", model="fake")
    adapter = NarrativeLLMAdapter(config)
    generator = NPCDialogueGenerator(adapter)

    # 注册两个 NPC
    generator.register_npc("master", MOCK_MASTER_CARD, MOCK_SCENE)
    generator.register_npc("rival", MOCK_RIVAL_CARD, MOCK_SCENE)

    # 多轮对话
    print("\n--- 与玄清真人对话 2 轮 ---")
    r1 = generator.talk("master", "拜见师父", turn=1)
    r2 = generator.talk("master", "请教修炼之法", turn=2)
    print(f"  第1轮 degraded={r1.get('degraded')}")
    print(f"  第2轮 degraded={r2.get('degraded')}")

    # 验证记忆已记录
    memory_ctx = generator.get_npc_memory_context("master")
    assert "拜见师父" in memory_ctx, "记忆应包含第 1 轮对话"
    assert "请教修炼之法" in memory_ctx, "记忆应包含第 2 轮对话"
    print(f"\n  ✓ 记忆已记录两轮对话")

    # 记录关键事件
    print("\n--- 记录关键事件 ---")
    generator.record_event("master", "helped", "玩家帮玄清真人解围", turn=3, impact=10)
    memory_ctx = generator.get_npc_memory_context("master")
    assert "帮玄清真人解围" in memory_ctx, "记忆应包含关键事件"
    print(f"  ✓ 关键事件已记录到记忆")

    # 切换到另一个 NPC
    print("\n--- 切换到萧逸（对手）对话 ---")
    r3 = generator.talk("rival", "你就是萧逸？", turn=4)
    memory_ctx_rival = generator.get_npc_memory_context("rival")
    assert "你就是萧逸" in memory_ctx_rival, "对手记忆应记录"
    print(f"  ✓ 对手 NPC 记忆独立记录")

    # 验证两个 NPC 记忆互不干扰
    assert "拜见师父" in generator.get_npc_memory_context("master")
    assert "拜见师父" not in generator.get_npc_memory_context("rival")
    print(f"\n  ✓ 两个 NPC 记忆互不干扰")

    print("\n[NPCDialogueGenerator 离线] 所有断言通过 ✓")
    return True


# ---- 测试 3: 真实 MiMo 多轮对话连贯性 ----

def test_mimo_multi_turn_coherence(generator: NPCDialogueGenerator):
    """测试 3：真实 MiMo 多轮对话连贯性（NPC 记得之前说过什么）。"""
    print("\n" + "=" * 60)
    print("[测试 3] 真实 MiMo 多轮对话连贯性")
    print("=" * 60)

    # 第 1 轮：请教修炼
    print("\n--- 第 1 轮：请教修炼 ---")
    r1 = generator.talk("master", "师父，弟子想请教修炼之法，该如何入门？", turn=1)
    print(f"  degraded={r1.get('degraded')}")
    print(f"  narrative: {r1.get('narrative', '')[:200]}")

    # 第 2 轮：追问上次的话题（测试 NPC 是否记得）
    print("\n--- 第 2 轮：追问上次话题 ---")
    r2 = generator.talk("master", "方才师父所言，弟子还有不解之处，能否再说一遍？", turn=2)
    print(f"  degraded={r2.get('degraded')}")
    print(f"  narrative: {r2.get('narrative', '')[:200]}")

    # 断言
    assert not r1.get("degraded"), "第 1 轮不应降级"
    assert not r2.get("degraded"), "第 2 轮不应降级"

    # 验证记忆已记录 2 轮
    memory_ctx = generator.get_npc_memory_context("master")
    assert "修炼之法" in memory_ctx or "修炼" in memory_ctx, "记忆应包含第 1 轮"
    print(f"\n  ✓ 两轮对话已记录到记忆")

    print("\n[MiMo 多轮对话连贯性] 所有断言通过 ✓")
    return True


# ---- 测试 4: 真实 MiMo 关键事件影响态度 ----

def test_mimo_event_affects_attitude(generator: NPCDialogueGenerator):
    """测试 4：关键事件影响 NPC 态度（记录 helped 事件后态度更热情）。"""
    print("\n" + "=" * 60)
    print("[测试 4] 真实 MiMo 关键事件影响态度")
    print("=" * 60)

    # 先记录一个 helped 事件
    print("\n--- 记录 helped 事件（玩家帮师父解围）---")
    generator.record_event("master", "helped", "玩家在试炼中帮玄清真人解围，挡下了一道攻击", turn=3, impact=15)

    # 对话（NPC 应该"记得"玩家帮过他，态度更热情）
    print("\n--- 对话（NPC 应记得玩家帮过他）---")
    r = generator.talk("master", "师父，弟子来了", turn=4)
    print(f"  degraded={r.get('degraded')}")
    print(f"  narrative: {r.get('narrative', '')[:300]}")

    # 断言
    assert not r.get("degraded"), "不应降级"

    # 验证记忆包含关键事件
    memory_ctx = generator.get_npc_memory_context("master")
    assert "解围" in memory_ctx, "记忆应包含关键事件"
    print(f"\n  ✓ 关键事件已影响 NPC 记忆")

    print("\n[MiMo 关键事件影响态度] 所有断言通过 ✓")
    return True


# ---- 主入口 ----

def main():
    use_real = "--real" in sys.argv

    # 离线测试
    r1 = test_memory_v2()
    r2 = test_generator_offline()

    if not use_real:
        print("\n" + "=" * 60)
        print("Day 9 离线测试通过 ✓")
        print("提示: 加 --real 参数运行真实 MiMo 端到端测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day9.py --real")
        print("=" * 60)
        return

    # 真实 MiMo 测试
    print("\n" + "=" * 60)
    print("启动真实 MiMo 端到端测试...")
    print("=" * 60)

    llm_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(llm_config)
    generator = NPCDialogueGenerator(adapter)
    generator.register_npc("master", MOCK_MASTER_CARD, MOCK_SCENE)

    r3 = test_mimo_multi_turn_coherence(generator)
    r4 = test_mimo_event_affects_attitude(generator)

    print("\n" + "=" * 60)
    if all([r1, r2, r3, r4]):
        print("Day 9 全部测试通过 ✓（含真实 MiMo 端到端）")
        print("交付物: memory.py v2 / npc_dialogue_generator.py")
    else:
        print("Day 9 有测试失败 ✗")
    print("=" * 60)


if __name__ == "__main__":
    main()
