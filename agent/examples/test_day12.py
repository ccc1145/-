"""Day 12 端到端测试：降级机制 + 内容安全过滤 + Parser 容错增强。

对齐 Day 12 任务：实现 Agent 输出降级 + 内容安全过滤 + Parser 容错增强。

测试覆盖：
1. FallbackProvider 场景级预设文案（5 个场景 + 对话/自由输入降级）
2. ContentFilter 内容安全过滤（blocked/warned/replaced 三级）
3. Parser 容错增强（嵌套对象提取 + 多行 JSON + 数值字段校验）
4. Controller 集成测试（LLM 输出过滤 + 降级文案正确）
5. 真实 MiMo 端到端（验证 content_filter 不误杀正常叙事）

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试（无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day12.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day12.py --real
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

from content_filter import filter_text, sanitize_llm_output, should_degrade_for_blocked  # noqa: E402
from fallback_provider import (  # noqa: E402
    build_dialogue_fallback,
    build_free_input_fallback,
    build_scene_fallback,
    get_scene_preset,
)
from parser import AgentOutputParser  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from narrative_controller import NarrativeController  # noqa: E402
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


# ---- 测试 1: FallbackProvider 场景级预设文案 ----

def test_fallback_provider():
    """测试 1：FallbackProvider 场景级预设文案。"""
    print("=" * 60)
    print("[测试 1] FallbackProvider 场景级预设文案")
    print("=" * 60)

    all_pass = True

    # 1.1 5 个场景的预设文案
    print("\n--- 1.1 场景预设文案覆盖 ---")
    scenes = ["trial_grounds", "trial_result", "sect_entrance", "cheng_yun_dian", "unknown_scene"]
    for sid in scenes:
        preset = get_scene_preset(sid, "scene_narrative")
        preset_dialogue = get_scene_preset(sid, "npc_dialogue")
        if preset and preset_dialogue:
            print(f"  ✓ [{sid}] scene_narrative: {preset[:30]}...")
            print(f"    [{sid}] npc_dialogue: {preset_dialogue[:30]}...")
        else:
            print(f"  ✗ [{sid}] 预设文案缺失")
            all_pass = False

    # 1.2 build_scene_fallback
    print("\n--- 1.2 build_scene_fallback ---")
    r = build_scene_fallback(scene_id="cheng_yun_dian", player_name="李逍遥", error="test")
    if r.get("degraded") and r.get("narrative") and len(r.get("available_choices", [])) >= 1:
        print(f"  ✓ degraded={r['degraded']}, narrative={r['narrative'][:30]}...")
    else:
        print(f"  ✗ build_scene_fallback 失败")
        all_pass = False

    # 1.3 build_dialogue_fallback
    print("\n--- 1.3 build_dialogue_fallback ---")
    r = build_dialogue_fallback(scene_id="cheng_yun_dian", npc_name="徐伯潜", error="test")
    if r.get("degraded") and "徐伯潜" in r.get("narrative", ""):
        print(f"  ✓ degraded={r['degraded']}, narrative={r['narrative'][:30]}...")
    else:
        print(f"  ✗ build_dialogue_fallback 失败")
        all_pass = False

    # 1.4 build_free_input_fallback
    print("\n--- 1.4 build_free_input_fallback ---")
    r = build_free_input_fallback(intent="provoke", scene_id="default", error="test")
    if r.get("degraded") and r.get("narrative"):
        print(f"  ✓ intent=provoke, narrative={r['narrative'][:30]}...")
    else:
        print(f"  ✗ build_free_input_fallback 失败")
        all_pass = False

    if all_pass:
        print("\n[FallbackProvider] 所有断言通过 ✓")
    else:
        print("\n[FallbackProvider] 有断言失败 ✗")
    return all_pass


# ---- 测试 2: ContentFilter 内容安全过滤 ----

def test_content_filter():
    """测试 2：ContentFilter 内容安全过滤。"""
    print("\n" + "=" * 60)
    print("[测试 2] ContentFilter 内容安全过滤")
    print("=" * 60)

    all_pass = True

    # 2.1 blocked 词检测（政治/色情/广告）
    print("\n--- 2.1 blocked 词检测 ---")
    blocked_cases = [
        ("天安门事件你知道吗", "政治敏感"),
        ("你这家伙真是个傻逼", "色情低俗"),
        ("加微信免费领取", "广告引流"),
    ]
    for text, desc in blocked_cases:
        result = filter_text(text)
        if result.is_blocked:
            print(f"  ✓ [{desc}] blocked={result.is_blocked}, words={result.blocked_words}")
        else:
            print(f"  ✗ [{desc}] 应 blocked 但未检测到")
            all_pass = False

    # 2.2 warned 词检测（暴力）
    print("\n--- 2.2 warned 词检测 ---")
    result = filter_text("他想要自杀")
    if result.is_warned and "自杀" in result.warned_words:
        print(f"  ✓ warned={result.is_warned}, words={result.warned_words}")
    else:
        print(f"  ✗ 应 warned 但未检测到")
        all_pass = False

    # 2.3 modern_slang 替换
    print("\n--- 2.3 modern_slang 替换 ---")
    result = filter_text("他说666，大佬真厉害")
    if result.has_replacement and "了得" in result.cleaned_text and "前辈" in result.cleaned_text:
        print(f"  ✓ cleaned: {result.cleaned_text}")
    else:
        print(f"  ✗ 替换失败, cleaned: {result.cleaned_text}")
        all_pass = False

    # 2.4 正常文本不误判
    print("\n--- 2.4 正常文本不误判 ---")
    result = filter_text("玄清真人抚须而立，目光微动，似有几分嘉许。")
    if not result.has_issue():
        print(f"  ✓ 正常文本无任何问题")
    else:
        print(f"  ✗ 正常文本被误判: {result.to_dict()}")
        all_pass = False

    # 2.5 sanitize_llm_output
    print("\n--- 2.5 sanitize_llm_output ---")
    # blocked 输出应返回空字符串
    cleaned, result = sanitize_llm_output("这段叙事含傻逼词")
    if not cleaned and result.is_blocked:
        print(f"  ✓ blocked 输出返回空字符串（触发降级）")
    else:
        print(f"  ✗ blocked 输出未正确处理")
        all_pass = False

    # modern_slang 输出应返回替换后的文本
    cleaned, result = sanitize_llm_output("他666啊")
    if cleaned == "他了得啊" and not result.is_blocked:
        print(f"  ✓ modern_slang 输出返回替换文本: {cleaned}")
    else:
        print(f"  ✗ modern_slang 输出处理异常, cleaned={cleaned}")
        all_pass = False

    if all_pass:
        print("\n[ContentFilter] 所有断言通过 ✓")
    else:
        print("\n[ContentFilter] 有断言失败 ✗")
    return all_pass


# ---- 测试 3: Parser 容错增强 ----

def test_parser_enhancements():
    """测试 3：Parser 容错增强（Day 12 新增策略）。"""
    print("\n" + "=" * 60)
    print("[测试 3] Parser 容错增强")
    print("=" * 60)

    parser = AgentOutputParser()
    all_pass = True

    # 3.1 嵌套对象提取
    print("\n--- 3.1 嵌套对象提取 ---")
    raw = '{"data": {"narrative": "嵌套叙事", "available_choices": [{"id": "a", "text": "A"}]}}'
    result = parser.parse(raw)
    if result.get("narrative") == "嵌套叙事" and not result.get("parse_failed"):
        print(f"  ✓ 嵌套对象提取成功, narrative={result['narrative']}")
    else:
        print(f"  ✗ 嵌套对象提取失败, narrative={result.get('narrative')}")
        all_pass = False

    # 3.2 多行 JSON（前后带说明，但 JSON 完整）
    print("\n--- 3.2 多行 JSON（前后带说明）---")
    raw = '好的，这是叙事：\n{"narrative": "带说明的叙事", "available_choices": [{"id": "a", "text": "A"}]}\n以上。'
    result = parser.parse(raw)
    if result.get("narrative") == "带说明的叙事" and not result.get("parse_failed"):
        print(f"  ✓ 多行 JSON 提取成功, narrative={result['narrative']}")
    else:
        print(f"  ✗ 多行 JSON 提取失败, narrative={result.get('narrative')}")
        all_pass = False

    # 3.3 数值字段类型校验
    print("\n--- 3.3 数值字段类型校验 ---")
    raw = '{"narrative": "数值测试", "state_changes": {"player": {"hp": "100", "mp": "50", "cultivation": "10"}}, "available_choices": [{"id": "a", "text": "A"}]}'
    result = parser.parse(raw)
    state = result.get("state_changes", {}).get("player", {})
    if isinstance(state.get("hp"), int) and state.get("hp") == 100:
        print(f"  ✓ 数值字段已转为 int: hp={state.get('hp')} (type={type(state.get('hp')).__name__})")
    else:
        print(f"  ✗ 数值字段未转为 int: hp={state.get('hp')} (type={type(state.get('hp')).__name__})")
        all_pass = False

    # 3.4 验证字符串字段不被错误转换
    print("\n--- 3.4 字符串字段不被错误转换 ---")
    raw = '{"narrative": "测试叙事", "state_changes": {"event": "触发了事件"}, "available_choices": [{"id": "a", "text": "A"}]}'
    result = parser.parse(raw)
    state = result.get("state_changes", {})
    if isinstance(state.get("event"), str) and state.get("event") == "触发了事件":
        print(f"  ✓ 字符串字段保留: event={state.get('event')}")
    else:
        print(f"  ✗ 字符串字段被错误转换: event={state.get('event')}")
        all_pass = False

    if all_pass:
        print("\n[Parser 容错增强] 所有断言通过 ✓")
    else:
        print("\n[Parser 容错增强] 有断言失败 ✗")
    return all_pass


# ---- 测试 4: Controller 集成测试 ----

def test_controller_integration():
    """测试 4：Controller 集成测试（LLM 输出过滤 + 降级文案）。"""
    print("\n" + "=" * 60)
    print("[测试 4] Controller 集成测试")
    print("=" * 60)

    all_pass = True

    # 4.1 FakeLLM 降级使用 fallback_provider
    print("\n--- 4.1 FakeLLM 降级使用 fallback_provider ---")
    fake_config = LLMConfig(provider="fake", model="fake")
    fake_adapter = NarrativeLLMAdapter(fake_config)
    controller = NarrativeController(fake_adapter, max_retries=1)

    result = controller.generate_scene_narrative(
        game_state={
            "player": {"name": "李逍遥", "cultivation": 0, "hp": 100, "mp": 50},
            "world": {"current_scene_id": "cheng_yun_dian", "flags": {}, "npc_affinity": {}},
        },
        current_scene={"id": "cheng_yun_dian", "name": "承运殿"},
        player_input={"text": "测试操作"},
        event_context={},
        memory={"recent_events": [], "dialogue_history": {}},
        npc_cards={},
    )

    if result.get("degraded") and "承运殿" in result.get("narrative", ""):
        print(f"  ✓ 场景叙事降级使用 fallback_provider")
        print(f"    narrative: {result['narrative'][:50]}...")
    else:
        print(f"  ✗ 场景叙事降级未使用 fallback_provider")
        print(f"    narrative: {result.get('narrative', '')[:50]}...")
        all_pass = False

    # 4.2 NPC 对话降级使用 fallback_provider
    print("\n--- 4.2 NPC 对话降级使用 fallback_provider ---")
    result = controller.generate_npc_dialogue(
        npc={"id": "xu_boqian", "name": "徐伯潜", "current_affinity": 0, "personality": {"traits": ["严厉"], "speaking_style": "测试"}},
        player_input={"text": "你好"},
        current_scene={"id": "cheng_yun_dian", "name": "承运殿"},
        dialogue_history=[],
    )

    if result.get("degraded") and "徐伯潜" in result.get("narrative", ""):
        print(f"  ✓ NPC 对话降级使用 fallback_provider")
        print(f"    narrative: {result['narrative'][:50]}...")
    else:
        print(f"  ✗ NPC 对话降级未使用 fallback_provider")
        all_pass = False

    if all_pass:
        print("\n[Controller 集成] 所有断言通过 ✓")
    else:
        print("\n[Controller 集成] 有断言失败 ✗")
    return all_pass


# ---- 测试 5: 真实 MiMo - content_filter 不误杀正常叙事 ----

def test_mimo_content_filter_no_false_positive(controller: NarrativeController):
    """测试 5：真实 MiMo - content_filter 不误杀正常叙事。"""
    print("\n" + "=" * 60)
    print("[测试 5] 真实 MiMo - content_filter 不误杀正常叙事")
    print("=" * 60)

    result = controller.generate_scene_narrative(
        game_state={
            "session_id": "day12-test",
            "turn_count": 1,
            "player": {
                "name": "李逍遥",
                "gender": "男",
                "spiritual_root": "火灵根",
                "cultivation": 0,
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
        },
        current_scene={
            "id": "trial_grounds",
            "name": "试炼场",
            "description": "试炼场中央立着一块古朴的测灵石",
            "mood": "庄严、期待",
        },
        player_input={"text": "触摸测灵石"},
        event_context={},
        memory={"recent_events": [], "dialogue_history": {}},
        npc_cards={},
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:300]}")

    # 断言
    assert not result.get("degraded"), "不应降级（正常叙事不应被 content_filter 误杀）"
    assert narrative, "narrative 不应为空"
    assert len(narrative) > 50, "narrative 应有足够长度"

    print("\n[MiMo content_filter 不误杀] 测试通过 ✓")
    return True


# ---- 主入口 ----

def main():
    use_real = "--real" in sys.argv

    # 离线测试
    r1 = test_fallback_provider()
    r2 = test_content_filter()
    r3 = test_parser_enhancements()
    r4 = test_controller_integration()

    if not use_real:
        print("\n" + "=" * 60)
        if all([r1, r2, r3, r4]):
            print("Day 12 离线测试通过 ✓")
        else:
            print("Day 12 有离线测试失败 ✗")
        print("提示: 加 --real 参数运行真实 MiMo 测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day12.py --real")
        print("=" * 60)
        return

    # 真实 MiMo 测试
    print("\n" + "=" * 60)
    print("启动真实 MiMo 测试...")
    print("=" * 60)

    llm_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(llm_config)
    controller = NarrativeController(adapter, max_retries=3)

    r5 = test_mimo_content_filter_no_false_positive(controller)

    print("\n" + "=" * 60)
    if all([r1, r2, r3, r4, r5]):
        print("Day 12 全部测试通过 ✓（含真实 MiMo）")
        print("交付物: fallback_provider + content_filter + parser 容错增强")
    else:
        print("Day 12 有测试失败 ✗")
    print("=" * 60)


if __name__ == "__main__":
    main()
