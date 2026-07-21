"""Day 11 端到端测试：格式错误修复 + 幻觉抑制 + 降级机制全测。

对齐 Day 11 任务：修复 Agent 格式错误 + 优化 Prompt 减少幻觉 + 测试降级机制。

测试覆盖：
1. Parser 容错增强（choice 子字段归一化 + segments type 枚举校验 + 白名单过滤）
2. 降级机制全测（空响应 / 纯文本 / 截断 JSON / 网络错误 / 3次重试全失败）
3. NPC 对话 response 空值兜底
4. 真实 MiMo 幻觉抑制（强化 knowledge 限制 + 明确拒答词）
5. 真实 MiMo GameState 依据（不编造玩家未达到的境界）

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试（无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day11.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day11.py --real
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

from parser import AgentOutputParser  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from narrative_controller import NarrativeController  # noqa: E402
from npc_dialogue_generator import NPCDialogueGenerator  # noqa: E402
from world_book_loader import WorldBookLoader, NPCCardLoader  # noqa: E402
from ai_agent_framework.config.settings import LLMConfig  # noqa: E402

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


# ---- 测试 1: Parser 容错增强 ----

def test_parser_enhancements():
    """测试 1：Parser 容错增强（Day 11 新增的 3 项修复）。"""
    print("=" * 60)
    print("[测试 1] Parser 容错增强")
    print("=" * 60)

    parser = AgentOutputParser()
    all_pass = True

    # 1.1 choice 子字段名归一化（choice_id / choice_text / key / label）
    print("\n--- 1.1 choice 子字段名归一化 ---")
    raw = '{"narrative":"测试","available_choices":[{"choice_id":"a","choice_text":"选项A"},{"key":"b","label":"选项B"}]}'
    result = parser.parse(raw)
    choices = result.get("available_choices", [])
    print(f"  输入: choice_id/choice_text, key/label")
    print(f"  输出: {choices}")
    if len(choices) == 2 and choices[0].get("id") == "a" and choices[0].get("text") == "选项A" \
       and choices[1].get("id") == "b" and choices[1].get("text") == "选项B":
        print("  ✓ choice 子字段归一化成功")
    else:
        print("  ✗ choice 子字段归一化失败")
        all_pass = False

    # 1.2 segments type 枚举校验（非标准值归一化为 narration）
    print("\n--- 1.2 segments type 枚举校验 ---")
    raw = '{"narrative":"测试","narrative_segments":[{"type":"描述","text":"非标准类型"},{"type":"dialogue","speaker":"玄清","text":"对话"},{"type":"narration","text":"旁白"}],"available_choices":[{"id":"a","text":"A"}]}'
    result = parser.parse(raw)
    segs = result.get("narrative_segments", [])
    types = [s.get("type") for s in segs]
    print(f"  输入 type: ['描述', 'dialogue', 'narration']")
    print(f"  输出 type: {types}")
    if types == ["narration", "dialogue", "narration"]:
        print("  ✓ 非标准 type 归一化为 narration 成功")
    else:
        print("  ✗ type 枚举校验失败")
        all_pass = False

    # 1.3 白名单过滤（删除 LLM 返回的非 schema 字段）
    print("\n--- 1.3 白名单过滤 ---")
    raw = '{"narrative":"测试","reasoning":"这是LLM的推理过程","explanation":"解释","available_choices":[{"id":"a","text":"A"}],"custom_field":"应被过滤"}'
    result = parser.parse(raw)
    print(f"  输入字段: {['narrative', 'reasoning', 'explanation', 'available_choices', 'custom_field']}")
    print(f"  输出字段: {list(result.keys())}")
    if "reasoning" not in result and "explanation" not in result and "custom_field" not in result:
        print("  ✓ 非 schema 字段已被过滤")
    else:
        print("  ✗ 白名单过滤失败")
        all_pass = False

    # 1.4 验证标准字段保留
    print("\n--- 1.4 标准字段保留 ---")
    if "narrative" in result and "available_choices" in result:
        print("  ✓ 标准字段保留成功")
    else:
        print("  ✗ 标准字段丢失")
        all_pass = False

    if all_pass:
        print("\n[Parser 容错增强] 所有断言通过 ✓")
    else:
        print("\n[Parser 容错增强] 有断言失败 ✗")
    return all_pass


# ---- 测试 2: 降级机制全测 ----

def test_degradation_mechanism():
    """测试 2：降级机制全测（模拟各种 LLM 失败场景）。"""
    print("\n" + "=" * 60)
    print("[测试 2] 降级机制全测")
    print("=" * 60)

    parser = AgentOutputParser()
    all_pass = True

    # 2.1 空响应
    print("\n--- 2.1 空响应降级 ---")
    result = parser.parse("")
    if result.get("degraded") and result.get("parse_failed"):
        print(f"  ✓ 空响应触发降级, narrative={result['narrative'][:30]}...")
    else:
        print(f"  ✗ 空响应未触发降级")
        all_pass = False

    # 2.2 纯文本无 JSON
    print("\n--- 2.2 纯文本降级 ---")
    result = parser.parse("LLM 出错了，这只是一段普通文本，没有任何 JSON 结构。")
    if result.get("degraded"):
        print(f"  ✓ 纯文本触发降级, narrative={result['narrative'][:30]}...")
    else:
        print(f"  ✗ 纯文本未触发降级")
        all_pass = False

    # 2.3 截断 JSON
    print("\n--- 2.3 截断 JSON 降级 ---")
    result = parser.parse('{"narrative":"被截断的叙事","available_choices":[{"id":"a","text":"A")')
    if result.get("degraded") or result.get("parse_failed"):
        print(f"  ✓ 截断 JSON 触发降级/补全, narrative={result.get('narrative','')[:30]}...")
    else:
        print(f"  ✗ 截断 JSON 未触发降级")
        all_pass = False

    # 2.4 缺 available_choices（应补全而非降级）
    print("\n--- 2.4 缺 available_choices 自动补全 ---")
    result = parser.parse('{"narrative":"正常叙事"}')
    if not result.get("degraded") and len(result.get("available_choices", [])) >= 1:
        print(f"  ✓ 缺 choices 自动补全为 {len(result['available_choices'])} 个兜底选项")
    else:
        print(f"  ✗ 缺 choices 处理异常")
        all_pass = False

    # 2.5 Controller 降级（FakeLLM 模式，3次重试全失败）
    print("\n--- 2.5 Controller 降级（FakeLLM 全失败）---")
    fake_config = LLMConfig(provider="fake", model="fake")
    fake_adapter = NarrativeLLMAdapter(fake_config)
    # max_retries=1 加快测试
    controller = NarrativeController(fake_adapter, max_retries=1)
    result = controller.generate_scene_narrative(
        game_state={
            "player": {"name": "测试者", "cultivation": 0, "hp": 100, "mp": 50},
            "world": {"current_scene_id": "test_scene", "flags": {}, "npc_affinity": {}},
        },
        current_scene={"id": "test_scene", "name": "测试场景"},
        player_input={"text": "测试操作"},
        event_context={},
        memory={"recent_events": [], "dialogue_history": {}},
        npc_cards={},
    )
    if result.get("degraded"):
        print(f"  ✓ Controller 降级成功, narrative={result['narrative'][:30]}...")
        print(f"    thought: {result.get('thought', '')[:60]}")
    else:
        print(f"  ✗ Controller 未降级")
        all_pass = False

    # 2.6 NPC 对话降级（FakeLLM 模式）
    print("\n--- 2.6 NPC 对话降级 ---")
    result = controller.generate_npc_dialogue(
        npc={"id": "test_npc", "name": "测试NPC", "current_affinity": 0, "personality": {"traits": ["测试"], "speaking_style": "测试"}},
        player_input={"text": "你好"},
        current_scene={"id": "test_scene", "name": "测试场景"},
        dialogue_history=[],
    )
    if result.get("degraded"):
        print(f"  ✓ NPC 对话降级成功, narrative={result['narrative'][:30]}...")
    else:
        print(f"  ✗ NPC 对话未降级")
        all_pass = False

    if all_pass:
        print("\n[降级机制] 所有断言通过 ✓")
    else:
        print("\n[降级机制] 有断言失败 ✗")
    return all_pass


# ---- 测试 3: NPC 对话 response 空值兜底 ----

def test_dialogue_response_fallback():
    """测试 3：NPC 对话 response 空值兜底。"""
    print("\n" + "=" * 60)
    print("[测试 3] NPC 对话 response 空值兜底")
    print("=" * 60)

    # 模拟 LLM 返回缺 response 的 JSON
    parsed = {"emotion": "困惑", "internal_thought": "不知道说什么"}
    npc = {"id": "master", "name": "玄清真人"}

    result = NarrativeController._normalize_dialogue_output(parsed, npc)

    print(f"  输入 parsed: {parsed}")
    print(f"  输出 narrative: {result['narrative']}")
    print(f"  输出 segments: {result['narrative_segments']}")

    if result["narrative"] and "玄清真人" in result["narrative"]:
        print("  ✓ response 空值兜底成功（narrative 非空且含 NPC 名）")
    else:
        print("  ✗ response 空值兜底失败")
        return False

    # 验证 segments 也有内容
    if result["narrative_segments"] and result["narrative_segments"][0].get("text"):
        print("  ✓ segments 兜底成功")
    else:
        print("  ✗ segments 兜底失败")
        return False

    print("\n[response 空值兜底] 所有断言通过 ✓")
    return True


# ---- 测试 4: 真实 MiMo 幻觉抑制 - knowledge 限制强化 ----

def test_mimo_knowledge_limit_enhanced(generator: NPCDialogueGenerator):
    """测试 4：真实 MiMo - knowledge 限制强化（Day 11 应让 NPC 明确说"不知"）。"""
    print("\n" + "=" * 60)
    print("[测试 4] 真实 MiMo - knowledge 限制强化（明确拒答）")
    print("=" * 60)

    # 徐伯潜 knowledge 不含"神武宗烈火诀"，期望 NPC 明确说"不知"
    result = generator.talk(
        "xu_boqian",
        "教习，神武宗的烈火诀第七式如何修炼？请详细告诉我。",
        turn=1,
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:400]}")

    assert not result.get("degraded"), "不应降级"
    assert narrative, "narrative 不应为空"

    # Day 11 强化后，NPC 应明确说"不知"类拒答词
    refusal_keywords = ["不知", "未闻", "非我所知", "此事非我所知", "你问错人", "不晓得", "不明白", "不熟", "不在行"]
    found_refusal = any(kw in narrative for kw in refusal_keywords)

    # 检查是否编造了烈火诀内容（幻觉）
    hallucination_keywords = ["烈火诀", "第七式", "火属", "经脉", "丹田"]
    found_hallucination = any(kw in narrative for kw in hallucination_keywords)

    if found_refusal:
        print(f"\n  ✓ knowledge 限制生效：NPC 明确拒答")
    else:
        print(f"\n  ⚠ NPC 未用标准拒答词（需人工审查是否委婉回避）")

    if found_hallucination:
        print(f"  ✗ 检测到幻觉：NPC 可能编造了烈火诀内容")
        return False

    print("\n[MiMo knowledge 限制强化] 测试通过 ✓")
    return True


# ---- 测试 5: 真实 MiMo GameState 依据 - 不编造境界 ----

def test_mimo_gamestate_adherence(generator: NPCDialogueGenerator):
    """测试 5：真实 MiMo - GameState 依据（不编造玩家未达到的境界）。"""
    print("\n" + "=" * 60)
    print("[测试 5] 真实 MiMo - GameState 依据（不编造境界）")
    print("=" * 60)

    # 玩家是初始状态（修为 0），问 NPC 自己什么时候能飞升
    # 期望 NPC 不会说"你已经飞升"或"你即将飞升"
    result = generator.talk(
        "xu_boqian",
        "教习，弟子何时能飞升仙界？",
        turn=2,
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:400]}")

    assert not result.get("degraded"), "不应降级"
    assert narrative, "narrative 不应为空"

    # 软断言：NPC 不应说玩家"已飞升"或"即将飞升"
    hallucination_keywords = ["你已飞升", "你即将飞升", "你已渡劫", "你已成仙"]
    found_hallucination = any(kw in narrative for kw in hallucination_keywords)

    if found_hallucination:
        print(f"\n  ✗ 检测到幻觉：NPC 可能编造了玩家境界")
        return False
    else:
        print(f"\n  ✓ GameState 依据生效：NPC 未编造玩家境界")

    print("\n[MiMo GameState 依据] 测试通过 ✓")
    return True


# ---- 主入口 ----

def main():
    use_real = "--real" in sys.argv

    # 离线测试
    r1 = test_parser_enhancements()
    r2 = test_degradation_mechanism()
    r3 = test_dialogue_response_fallback()

    if not use_real:
        print("\n" + "=" * 60)
        if all([r1, r2, r3]):
            print("Day 11 离线测试通过 ✓")
        else:
            print("Day 11 有离线测试失败 ✗")
        print("提示: 加 --real 参数运行真实 MiMo 幻觉抑制测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day11.py --real")
        print("=" * 60)
        return

    # 真实 MiMo 测试
    print("\n" + "=" * 60)
    print("启动真实 MiMo 幻觉抑制测试...")
    print("=" * 60)

    llm_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(llm_config)

    wb_loader = WorldBookLoader()
    wb_loader.load_all()
    npc_loader = NPCCardLoader()
    npc_loader.load_all()

    generator = NPCDialogueGenerator(adapter, world_book_loader=wb_loader)
    xu_card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    scene = {"id": "cheng_yun_dian", "name": "承运殿", "description": "扶龙宫讲学所在"}
    generator.register_npc("xu_boqian", xu_card, scene)

    r4 = test_mimo_knowledge_limit_enhanced(generator)
    r5 = test_mimo_gamestate_adherence(generator)

    print("\n" + "=" * 60)
    if all([r1, r2, r3, r4, r5]):
        print("Day 11 全部测试通过 ✓（含真实 MiMo 幻觉抑制）")
        print("交付物: Parser 容错增强 + Prompt 反幻觉守则 + 降级机制全测")
    else:
        print("Day 11 有测试失败 ✗")
    print("=" * 60)


if __name__ == "__main__":
    main()
