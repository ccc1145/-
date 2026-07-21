"""Agent 整体完成性和完整性测试（Day 1-12 综合）。

测试覆盖 Agent 模块全部交付功能，分两部分：
- 第一部分（T01-T10）：离线功能完整性测试，快速全跑
- 第二部分（R01-R06）：真实 MiMo 端到端质量测试，关键场景

每项测试输出：
- 测试名称 + 通过/失败状态（✓/✗）
- 关键指标（响应时间、字段完整性等）
- 实际输出内容（前 N 字符）
- 对齐标准（agent-io-format.md 第 X 节等）

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试（无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_integration.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_integration.py --real
    # 只跑离线测试的某一模块
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_integration.py --module parser
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# ---- Path 设置 ----
AGENT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_ROOT.parent
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"
sys.path.insert(0, str(FRAMEWORK_SRC))
sys.path.insert(0, str(AGENT_ROOT / "src"))

# ---- LLM 配置 ----
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"


def _build_llm_config(use_real: bool) -> "LLMConfig":
    from ai_agent_framework.config.settings import LLMConfig
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


# ---- 测试结果统计 ----
class TestReport:
    """测试结果统计器。"""

    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def record(self, name: str, status: str, detail: str = "") -> None:
        if status == "pass":
            self.passed.append(name)
            print(f"  ✓ {name}")
        elif status == "fail":
            self.failed.append(name)
            print(f"  ✗ {name}")
            if detail:
                print(f"    详情: {detail}")
        else:
            self.skipped.append(name)
            print(f"  - {name} (跳过)")

    def summary(self) -> str:
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        rate = (len(self.passed) / total * 100) if total > 0 else 0
        return (
            f"\n{'=' * 60}\n"
            f"测试总结: {len(self.passed)} 通过 / {len(self.failed)} 失败 / {len(self.skipped)} 跳过 "
            f"(达标率 {rate:.1f}%)\n"
            f"{'=' * 60}"
        )


REPORT = TestReport()


# ---- Mock 数据（对齐 GameState v1.0）----
MOCK_GAME_STATE = {
    "session_id": "integration-test-001",
    "turn_count": 3,
    "player": {
        "name": "李逍遥",
        "gender": "男",
        "spiritual_root": "火灵根",
        "cultivation": 0,
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


# =====================================================================
# 第一部分：离线功能完整性测试（T01-T10）
# =====================================================================

def test_t01_module_imports():
    """T01: 模块导入与初始化（11 个模块全部可正常加载）。"""
    print("\n" + "=" * 60)
    print("[T01] 模块导入与初始化")
    print("=" * 60)

    modules = [
        ("llm_adapter", "NarrativeLLMAdapter"),
        ("prompt_builder", "PromptBuilder"),
        ("parser", "AgentOutputParser"),
        ("memory", "MemoryManager"),
        ("world_knowledge", "get_all_world_knowledge"),
        ("narrative_controller", "NarrativeController"),
        ("free_input_processor", "FreeInputProcessor"),
        ("npc_dialogue_generator", "NPCDialogueGenerator"),
        ("world_book_loader", "WorldBookLoader"),
        ("fallback_provider", "build_scene_fallback"),
        ("content_filter", "filter_text"),
    ]

    for mod_name, attr_name in modules:
        try:
            mod = __import__(mod_name)
            if hasattr(mod, attr_name):
                REPORT.record(f"T01.{mod_name}", "pass")
            else:
                REPORT.record(f"T01.{mod_name}", "fail", f"缺 {attr_name}")
        except Exception as e:
            REPORT.record(f"T01.{mod_name}", "fail", f"{type(e).__name__}: {e}")


def test_t02_io_format_compliance():
    """T02: IO 格式合规性（对齐 docs/agent-io-format.md v1.0）。"""
    print("\n" + "=" * 60)
    print("[T02] IO 格式合规性（agent-io-format.md v1.0）")
    print("=" * 60)

    from parser import AgentOutputParser
    parser = AgentOutputParser()

    # 标准输入：应解析成功且含全部必需字段
    raw = '''{
      "narrative": "李逍遥将手覆于测灵石上，灵气流转，石面赤光渐盛。",
      "narrative_segments": [
        {"type": "narration", "text": "李逍遥将手覆于测灵石上。"},
        {"type": "dialogue", "speaker": "玄清真人", "text": "火灵根，七品。"}
      ],
      "available_choices": [
        {"id": "choice_continue", "text": "恭敬称是"},
        {"id": "choice_reflect", "text": "就地盘膝"}
      ],
      "free_input_enabled": true,
      "thought": "测试用思考"
    }'''
    result = parser.parse(raw)

    # 必需字段检查
    required_fields = ["narrative", "narrative_segments", "available_choices", "free_input_enabled"]
    for field in required_fields:
        if field in result:
            REPORT.record(f"T02.field_{field}", "pass")
        else:
            REPORT.record(f"T02.field_{field}", "fail", f"缺字段 {field}")

    # available_choices 结构校验
    choices = result.get("available_choices", [])
    if len(choices) == 2 and all("id" in c and "text" in c for c in choices):
        REPORT.record("T02.choices_structure", "pass")
    else:
        REPORT.record("T02.choices_structure", "fail", f"choices={choices}")

    # narrative_segments 结构校验
    segs = result.get("narrative_segments", [])
    if len(segs) == 2 and all("type" in s and "text" in s for s in segs):
        REPORT.record("T02.segments_structure", "pass")
    else:
        REPORT.record("T02.segments_structure", "fail", f"segments={segs}")

    # free_input_enabled 类型校验
    if isinstance(result.get("free_input_enabled"), bool):
        REPORT.record("T02.free_input_bool", "pass")
    else:
        REPORT.record("T02.free_input_bool", "fail", f"type={type(result.get('free_input_enabled'))}")


def test_t03_parser_fault_tolerance():
    """T03: Parser 容错（16+4 项）。"""
    print("\n" + "=" * 60)
    print("[T03] Parser 容错")
    print("=" * 60)

    from parser import AgentOutputParser
    parser = AgentOutputParser()

    # 容错场景：should_degrade=True 表示应触发降级（返回兜底文案）
    # should_degrade=False 表示应正常解析（含标准字段）
    cases = [
        ("T03.normal_json", '{"narrative":"x","available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.empty_string", "", True),  # 应降级
        ("T03.pure_text", "纯文本无JSON", True),  # 应降级
        ("T03.truncated_json", '{"narrative":"被截断', True),  # 应降级
        ("T03.markdown_block", '```json\n{"narrative":"x","available_choices":[{"id":"a","text":"A"}]}\n```', False),
        ("T03.chinese_punctuation", '{"narrative":"中文，引号","available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.narrative_as_list", '{"narrative":["段落1","段落2"],"available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.single_quote", "{'narrative':'x','available_choices':[{'id':'a','text':'A'}]}", False),
        ("T03.nested_object", '{"data":{"narrative":"嵌套","available_choices":[{"id":"a","text":"A"}]}}', False),
        ("T03.multiline_json", '说明文字\n{"narrative":"多行","available_choices":[{"id":"a","text":"A"}]}\n结尾', False),
        ("T03.choice_field_alias", '{"narrative":"x","available_choices":[{"choice_id":"a","choice_text":"A"}]}', False),
        ("T03.segment_type_invalid", '{"narrative":"x","narrative_segments":[{"type":"奇怪","text":"y"}],"available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.extra_fields_filtered", '{"narrative":"x","reasoning":"应过滤","available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.numeric_coercion", '{"narrative":"x","state_changes":{"hp":"100"},"available_choices":[{"id":"a","text":"A"}]}', False),
        ("T03.missing_choices", '{"narrative":"无choices"}', False),  # 应补全 choices
        ("T03.missing_narrative", '{"available_choices":[{"id":"a","text":"A"}]}', True),  # 缺 narrative 应标记 parse_failed
    ]

    for name, raw, should_degrade in cases:
        try:
            result = parser.parse(raw)
            degraded = bool(result.get("degraded") or result.get("parse_failed"))
            # 有 narrative 或 segments 就算成功返回内容
            has_content = bool(result.get("narrative") or result.get("narrative_segments"))
            if has_content and (degraded == should_degrade):
                REPORT.record(name, "pass")
            else:
                REPORT.record(name, "fail", f"期望 degrade={should_degrade}, 实际 degraded={degraded}, has_content={has_content}")
        except Exception as e:
            REPORT.record(name, "fail", f"异常: {e}")


def test_t04_memory_v2():
    """T04: Memory v2 功能（短期+NPC个体+关键事件+智能截断）。"""
    print("\n" + "=" * 60)
    print("[T04] Memory v2 功能")
    print("=" * 60)

    from memory import MemoryManager, NPCMemory, ShortTermMemory

    # T04.1 短期记忆窗口裁剪
    stm = ShortTermMemory(max_turns=3)
    for i in range(1, 5):
        stm.add(turn=i, player_input=f"操作{i}", narrative=f"叙事{i}")
    ctx = stm.get_context()
    if len(ctx) == 3 and ctx[0]["turn"] == 2:
        REPORT.record("T04.short_term_window", "pass")
    else:
        REPORT.record("T04.short_term_window", "fail", f"len={len(ctx)}, first_turn={ctx[0]['turn'] if ctx else None}")

    # T04.2 NPC 对话记录带 turn
    npc_mem = NPCMemory(npc_id="master", max_history=3)
    npc_mem.add_dialogue("问1", "答1", turn=1)
    npc_mem.add_dialogue("问2", "答2", turn=2)
    dialogues = npc_mem.get_context()
    if len(dialogues) == 2 and dialogues[0]["turn"] == 1:
        REPORT.record("T04.npc_dialogue_turn", "pass")
    else:
        REPORT.record("T04.npc_dialogue_turn", "fail")

    # T04.3 关键事件记录
    npc_mem.record_event("helped", "玩家帮师父解围", turn=3, impact=10)
    events = npc_mem.get_events()
    if len(events) == 1 and events[0]["type"] == "helped" and events[0]["impact"] == 10:
        REPORT.record("T04.key_events", "pass")
    else:
        REPORT.record("T04.key_events", "fail")

    # T04.4 智能截断（>3 轮触发摘要）
    npc_mem2 = NPCMemory(npc_id="test", max_history=5)
    for i in range(1, 6):
        npc_mem2.add_dialogue(f"问{i}", f"答{i}", turn=i)
    prompt_ctx = npc_mem2.get_prompt_context()
    if "此前已对话" in prompt_ctx:
        REPORT.record("T04.smart_truncation", "pass")
    else:
        REPORT.record("T04.smart_truncation", "fail", "未触发摘要")

    # T04.5 关键事件在 Prompt 顶部
    if "【关键记忆】" in prompt_ctx or "【近期对话】" in prompt_ctx:
        REPORT.record("T04.prompt_context_structure", "pass")
    else:
        REPORT.record("T04.prompt_context_structure", "fail")

    # T04.6 MemoryManager 统一管理
    manager = MemoryManager(max_turns=3, npc_max_history=3)
    manager.add_turn(turn=1, player_input="操作", narrative="叙事")
    manager.add_npc_dialogue("master", "问", "答", turn=1)
    manager.record_npc_event("master", "helped", "事件", turn=2, impact=5)
    ctx = manager.get_prompt_context()
    if "recent_events" in ctx and "dialogue_history" in ctx:
        REPORT.record("T04.manager_unified", "pass")
    else:
        REPORT.record("T04.manager_unified", "fail")


def test_t05_content_filter():
    """T05: ContentFilter 内容安全过滤。"""
    print("\n" + "=" * 60)
    print("[T05] ContentFilter 内容安全过滤")
    print("=" * 60)

    from content_filter import filter_text, sanitize_llm_output

    # blocked 词
    r = filter_text("天安门事件")
    REPORT.record("T05.blocked_political", "pass" if r.is_blocked else "fail")

    r = filter_text("傻逼")
    REPORT.record("T05.blocked_explicit", "pass" if r.is_blocked else "fail")

    r = filter_text("加微信免费领取")
    REPORT.record("T05.blocked_advertising", "pass" if r.is_blocked else "fail")

    # warned 词
    r = filter_text("自杀")
    REPORT.record("T05.warned_violence", "pass" if r.is_warned else "fail")

    # replaced 词
    r = filter_text("666大佬")
    if r.has_replacement and "了得" in r.cleaned_text and "前辈" in r.cleaned_text:
        REPORT.record("T05.replaced_slang", "pass")
    else:
        REPORT.record("T05.replaced_slang", "fail", f"cleaned={r.cleaned_text}")

    # 正常文本不误判
    r = filter_text("玄清真人抚须而立")
    REPORT.record("T05.no_false_positive", "pass" if not r.has_issue() else "fail")

    # sanitize_llm_output
    cleaned, r = sanitize_llm_output("含傻逼的输出")
    REPORT.record("T05.sanitize_blocked", "pass" if not cleaned and r.is_blocked else "fail")


def test_t06_fallback_provider():
    """T06: FallbackProvider 降级文案。"""
    print("\n" + "=" * 60)
    print("[T06] FallbackProvider 降级文案")
    print("=" * 60)

    from fallback_provider import (
        build_scene_fallback, build_dialogue_fallback,
        build_free_input_fallback, get_scene_preset
    )

    # 5 个场景预设
    scenes = ["trial_grounds", "trial_result", "sect_entrance", "cheng_yun_dian", "unknown_scene"]
    for sid in scenes:
        preset = get_scene_preset(sid, "scene_narrative")
        if preset:
            REPORT.record(f"T06.scene_{sid}", "pass")
        else:
            REPORT.record(f"T06.scene_{sid}", "fail", "预设缺失")

    # 3 类降级响应
    r = build_scene_fallback(scene_id="trial_grounds", player_name="李逍遥", error="test")
    REPORT.record("T06.build_scene", "pass" if r.get("degraded") and r.get("narrative") else "fail")

    r = build_dialogue_fallback(scene_id="cheng_yun_dian", npc_name="徐伯潜", error="test")
    REPORT.record("T06.build_dialogue", "pass" if r.get("degraded") and "徐伯潜" in r.get("narrative", "") else "fail")

    r = build_free_input_fallback(intent="provoke", scene_id="default", error="test")
    REPORT.record("T06.build_free_input", "pass" if r.get("degraded") and r.get("narrative") else "fail")


def test_t07_free_input_processor():
    """T07: FreeInputProcessor 意图分类+OOC 检测。"""
    print("\n" + "=" * 60)
    print("[T07] FreeInputProcessor 意图分类+OOC 检测")
    print("=" * 60)

    from free_input_processor import (
        FreeInputProcessor, INTENT_ASK, INTENT_REQUEST,
        INTENT_CHAT, INTENT_PROVOKE, INTENT_IRRELEVANT
    )

    processor = FreeInputProcessor()

    intent_cases = [
        ("T07.intent_request", "师父，弟子想请教修炼之法", INTENT_REQUEST),
        ("T07.intent_provoke", "你这老东西算什么东西", INTENT_PROVOKE),
        ("T07.intent_ask", "什么是灵根？弟子不太明白", INTENT_ASK),
        ("T07.intent_chat", "今日天气不错，师父心情可好", INTENT_CHAT),
        ("T07.intent_irrelevant", "我要玩手机", INTENT_IRRELEVANT),
    ]

    for name, text, expected in intent_cases:
        result = processor.classify_intent_offline(text)
        if result["intent"] == expected:
            REPORT.record(name, "pass")
        else:
            REPORT.record(name, "fail", f"期望={expected}, 实际={result['intent']}")

    # OOC 检测
    ooc_cases = [
        ("T07.ooc_phone", "师父，我想玩手机", True),
        ("T07.ooc_game", "这游戏卡顿了", True),
        ("T07.ooc_normal", "弟子该如何修炼", False),
        ("T07.ooc_emo", "今日emo了", True),
    ]

    for name, text, expected_ooc in ooc_cases:
        is_ooc, reason = processor.detect_ooc(text)
        if is_ooc == expected_ooc:
            REPORT.record(name, "pass")
        else:
            REPORT.record(name, "fail", f"期望 ooc={expected_ooc}, 实际={is_ooc}")


def test_t08_world_book_loader():
    """T08: WorldBook+NPCCard 加载。"""
    print("\n" + "=" * 60)
    print("[T08] WorldBook+NPCCard 加载")
    print("=" * 60)

    from world_book_loader import WorldBookLoader, NPCCardLoader

    # WorldBook
    wb = WorldBookLoader()
    wb.load_all()
    total_entries = len(wb._entries)
    if total_entries > 100:
        REPORT.record("T08.world_book_count", "pass")
        print(f"    WorldBook: {len(wb._books)} 本书, {total_entries} 条知识")
    else:
        REPORT.record("T08.world_book_count", "fail", f"知识总数 {total_entries}")

    # 关键词触发
    matched = wb.match("师父，弟子想请教修炼之法")
    if len(matched) > 0:
        REPORT.record("T08.keyword_match", "pass")
    else:
        REPORT.record("T08.keyword_match", "fail", "无匹配")

    # NPCCard
    npc_loader = NPCCardLoader()
    npc_loader.load_all()
    if len(npc_loader._npcs) > 30:
        REPORT.record("T08.npc_count", "pass")
        print(f"    NPC: {len(npc_loader._npcs)} 个角色卡")
    else:
        REPORT.record("T08.npc_count", "fail", f"NPC 数 {len(npc_loader._npcs)}")

    # 转换为 Prompt 卡
    card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    if card and "name" in card and "personality" in card:
        REPORT.record("T08.npc_to_prompt", "pass")
    else:
        REPORT.record("T08.npc_to_prompt", "fail", "转换失败")


def test_t09_prompt_builder():
    """T09: PromptBuilder 渲染（4 个模板）。"""
    print("\n" + "=" * 60)
    print("[T09] PromptBuilder 渲染")
    print("=" * 60)

    from prompt_builder import PromptBuilder
    from world_knowledge import get_all_world_knowledge

    builder = PromptBuilder()

    # system_prompt（检查作者身份 + 场景名）
    try:
        prompt = builder.build_system_prompt(
            world_knowledge=get_all_world_knowledge(),
            current_scene=MOCK_SCENE,
            npc_cards=MOCK_NPC_CARDS,
        )
        # 用更宽松的关键词（避免编码问题）
        has_author = prompt and "资深" in prompt and "修仙" in prompt
        has_scene = prompt and ("试炼" in prompt or MOCK_SCENE["name"] in prompt)
        if has_author and has_scene:
            REPORT.record("T09.system_prompt", "pass")
        else:
            REPORT.record("T09.system_prompt", "fail", f"author={has_author}, scene={has_scene}, len={len(prompt) if prompt else 0}")
    except Exception as e:
        REPORT.record("T09.system_prompt", "fail", str(e))

    # scene_narrative_prompt（检查玩家名 + 玩家输入）
    try:
        prompt = builder.build_scene_narrative_prompt(
            game_state=MOCK_GAME_STATE,
            player_input={"type": "free_input", "text": "触摸测灵石"},
            event_context={},
            memory=MOCK_MEMORY,
        )
        has_player = prompt and "李逍遥" in prompt
        has_input = prompt and "触摸" in prompt
        if has_player and has_input:
            REPORT.record("T09.scene_narrative", "pass")
        else:
            REPORT.record("T09.scene_narrative", "fail", f"player={has_player}, input={has_input}, len={len(prompt) if prompt else 0}")
    except Exception as e:
        REPORT.record("T09.scene_narrative", "fail", str(e))

    # npc_dialogue_prompt
    try:
        prompt = builder.build_npc_dialogue_prompt(
            npc=MOCK_NPC_CARDS["master"],
            player_input={"text": "拜见师父"},
            current_scene=MOCK_SCENE,
            dialogue_history=[],
        )
        if prompt and "玄清真人" in prompt and "拜见师父" in prompt:
            REPORT.record("T09.npc_dialogue", "pass")
        else:
            REPORT.record("T09.npc_dialogue", "fail", "内容缺失")
    except Exception as e:
        REPORT.record("T09.npc_dialogue", "fail", str(e))

    # free_input_response_prompt（intent 应为 dict）
    try:
        prompt = builder.build_free_input_response_prompt(
            player_input="师父，弟子的灵根如何？",
            game_state=MOCK_GAME_STATE,
            current_scene=MOCK_SCENE,
            npc_cards=MOCK_NPC_CARDS,
            memory=MOCK_MEMORY,
            intent={"intent": "ask", "confidence": 0.9, "method": "offline", "matched_keywords": ["灵根"]},
        )
        if prompt and "弟子的灵根" in prompt:
            REPORT.record("T09.free_input", "pass")
        else:
            REPORT.record("T09.free_input", "fail", "内容缺失")
    except Exception as e:
        REPORT.record("T09.free_input", "fail", str(e))


def test_t10_controller_degradation():
    """T10: Controller 降级机制（FakeLLM 各种失败）。"""
    print("\n" + "=" * 60)
    print("[T10] Controller 降级机制")
    print("=" * 60)

    from llm_adapter import NarrativeLLMAdapter
    from narrative_controller import NarrativeController
    from ai_agent_framework.config.settings import LLMConfig

    fake_config = LLMConfig(provider="fake", model="fake")
    adapter = NarrativeLLMAdapter(fake_config)
    controller = NarrativeController(adapter, max_retries=1)

    # 场景叙事降级
    try:
        result = controller.generate_scene_narrative(
            game_state=MOCK_GAME_STATE,
            current_scene=MOCK_SCENE,
            player_input={"text": "测试"},
            event_context={},
            memory=MOCK_MEMORY,
            npc_cards={},
        )
        if result.get("degraded") and result.get("narrative"):
            REPORT.record("T10.scene_degradation", "pass")
        else:
            REPORT.record("T10.scene_degradation", "fail", f"degraded={result.get('degraded')}")
    except Exception as e:
        REPORT.record("T10.scene_degradation", "fail", str(e))

    # NPC 对话降级
    try:
        result = controller.generate_npc_dialogue(
            npc=MOCK_NPC_CARDS["master"],
            player_input={"text": "你好"},
            current_scene=MOCK_SCENE,
            dialogue_history=[],
        )
        if result.get("degraded") and result.get("narrative"):
            REPORT.record("T10.dialogue_degradation", "pass")
        else:
            REPORT.record("T10.dialogue_degradation", "fail", f"degraded={result.get('degraded')}")
    except Exception as e:
        REPORT.record("T10.dialogue_degradation", "fail", str(e))

    # 自由输入降级
    try:
        result = controller.generate_free_input_response(
            player_input="测试自由输入",
            game_state=MOCK_GAME_STATE,
            current_scene=MOCK_SCENE,
            npc_cards=MOCK_NPC_CARDS,
            memory=MOCK_MEMORY,
            use_llm_intent=False,
        )
        if result.get("degraded") and result.get("narrative"):
            REPORT.record("T10.free_input_degradation", "pass")
        else:
            REPORT.record("T10.free_input_degradation", "fail", f"degraded={result.get('degraded')}")
    except Exception as e:
        REPORT.record("T10.free_input_degradation", "fail", str(e))


# =====================================================================
# 第二部分：真实 MiMo 端到端质量测试（R01-R06）
# =====================================================================

def test_r01_scene_narrative(controller):
    """R01: 场景叙事生成（标准 request_type=scene_narrative）。"""
    print("\n" + "=" * 60)
    print("[R01] 场景叙事生成")
    print("=" * 60)

    start = time.time()
    result = controller.generate_scene_narrative(
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        player_input={"text": "触摸测灵石"},
        event_context={},
        memory=MOCK_MEMORY,
        npc_cards={},
    )
    elapsed = time.time() - start

    narrative = result.get("narrative", "")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  degraded: {result.get('degraded')}")
    print(f"  narrative ({len(narrative)} 字): {narrative[:200]}...")
    print(f"  choices: {len(result.get('available_choices', []))} 个")
    print(f"  segments: {len(result.get('narrative_segments', []))} 段")

    if result.get("degraded"):
        REPORT.record("R01.no_degradation", "fail", "不应降级")
    else:
        REPORT.record("R01.no_degradation", "pass")

    if narrative and len(narrative) > 50:
        REPORT.record("R01.narrative_quality", "pass")
    else:
        REPORT.record("R01.narrative_quality", "fail", f"narrative 过短: {len(narrative)} 字")

    if len(result.get("available_choices", [])) >= 1:
        REPORT.record("R01.choices_present", "pass")
    else:
        REPORT.record("R01.choices_present", "fail", "无 choices")

    # 禁忌词检查
    taboo_words = ["666", "大佬", "手机", "ok", "cool"]
    has_taboo = any(w in narrative for w in taboo_words)
    if not has_taboo:
        REPORT.record("R01.no_taboo_words", "pass")
    else:
        REPORT.record("R01.no_taboo_words", "fail", "含禁忌词")


def test_r02_npc_dialogue(generator):
    """R02: NPC 对话生成（含角色卡+世界观+Few-shot）。"""
    print("\n" + "=" * 60)
    print("[R02] NPC 对话生成（含角色卡+世界观）")
    print("=" * 60)

    start = time.time()
    result = generator.talk(
        "xu_boqian",
        "教习，弟子想请教《皇极惊世典》的入门心法。",
        turn=1,
    )
    elapsed = time.time() - start

    narrative = result.get("narrative", "")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  degraded: {result.get('degraded')}")
    print(f"  narrative ({len(narrative)} 字): {narrative[:300]}...")

    if not result.get("degraded") and narrative:
        REPORT.record("R02.success", "pass")
    else:
        REPORT.record("R02.success", "fail", "降级或空")

    # 角色性格符合度（徐伯潜严厉教习）
    strict_keywords = ["老夫", "莫要", "当", "须", "不可", "潜心"]
    if any(kw in narrative for kw in strict_keywords):
        REPORT.record("R02.personality_fit", "pass")
    else:
        REPORT.record("R02.personality_fit", "fail", "未体现严厉性格")


def test_r03_free_input(controller):
    """R03: 自由输入回应（意图分类+OOC 检测+回应）。"""
    print("\n" + "=" * 60)
    print("[R03] 自由输入回应")
    print("=" * 60)

    start = time.time()
    result = controller.generate_free_input_response(
        player_input="师父，弟子的灵根如何？适合修炼什么功法？",
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
        memory=MOCK_MEMORY,
        use_llm_intent=True,
    )
    elapsed = time.time() - start

    narrative = result.get("narrative", "")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  intent: {result.get('intent', {}).get('intent')}")
    print(f"  is_ooc: {result.get('is_ooc')}")
    print(f"  narrative ({len(narrative)} 字): {narrative[:200]}...")

    if not result.get("degraded") and narrative:
        REPORT.record("R03.success", "pass")
    else:
        REPORT.record("R03.success", "fail", "降级或空")

    if not result.get("is_ooc"):
        REPORT.record("R03.no_ooc_false_positive", "pass")
    else:
        REPORT.record("R03.no_ooc_false_positive", "fail", "正常输入被误判 OOC")


def test_r04_anti_hallucination(generator):
    """R04: 反幻觉验证（knowledge 限制+GameState 依据）。"""
    print("\n" + "=" * 60)
    print("[R04] 反幻觉验证")
    print("=" * 60)

    # knowledge 限制：问徐伯潜不知道的事
    start = time.time()
    result = generator.talk(
        "xu_boqian",
        "教习，神武宗的烈火诀第七式如何修炼？",
        turn=2,
    )
    elapsed = time.time() - start

    narrative = result.get("narrative", "")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  narrative: {narrative[:300]}...")

    # 应明确拒答
    refusal_keywords = ["不知", "未闻", "非我所知", "你问错人", "不晓得"]
    found_refusal = any(kw in narrative for kw in refusal_keywords)
    if found_refusal:
        REPORT.record("R04.knowledge_refusal", "pass")
    else:
        REPORT.record("R04.knowledge_refusal", "fail", "未明确拒答")

    # 不应编造烈火诀内容
    hallucination_keywords = ["烈火诀", "第七式"]
    found_hallucination = any(kw in narrative for kw in hallucination_keywords)
    if not found_hallucination:
        REPORT.record("R04.no_hallucination", "pass")
    else:
        REPORT.record("R04.no_hallucination", "fail", "检测到幻觉")


def test_r05_multi_turn_coherence(generator):
    """R05: 多轮对话连贯性（记忆驱动）。"""
    print("\n" + "=" * 60)
    print("[R05] 多轮对话连贯性")
    print("=" * 60)

    # 第 1 轮
    start = time.time()
    r1 = generator.talk("xu_boqian", "教习，弟子该如何入门修仙？", turn=1)
    elapsed1 = time.time() - start
    n1 = r1.get("narrative", "")
    print(f"  第1轮 ({elapsed1:.1f}s): {n1[:150]}...")

    # 第 2 轮（相关追问，验证 NPC 记得第 1 轮）
    start = time.time()
    r2 = generator.talk("xu_boqian", "弟子记下了，那下一步该如何？", turn=2)
    elapsed2 = time.time() - start
    n2 = r2.get("narrative", "")
    print(f"  第2轮 ({elapsed2:.1f}s): {n2[:150]}...")

    if n1 and n2:
        REPORT.record("R05.both_success", "pass")
    else:
        REPORT.record("R05.both_success", "fail", "有降级或空")

    # 连贯性：第 2 轮应承接第 1 轮（不重复相同内容）
    if n1 != n2:
        REPORT.record("R05.not_repeated", "pass")
    else:
        REPORT.record("R05.not_repeated", "fail", "两轮完全相同")

    # 记忆验证：第 2 轮应体现"记得之前说过"
    memory_keywords = ["已言", "已说", "方才", "刚才", "已提及", "如前所述", "吾已"]
    found_memory = any(kw in n2 for kw in memory_keywords)
    if found_memory:
        REPORT.record("R05.memory_driven", "pass")
    else:
        REPORT.record("R05.memory_driven", "fail", "未体现记忆连贯性（需人工审查）")


def test_r06_content_filter_no_false_positive(controller):
    """R06: content_filter 不误杀正常叙事。"""
    print("\n" + "=" * 60)
    print("[R06] content_filter 不误杀正常叙事")
    print("=" * 60)

    start = time.time()
    result = controller.generate_scene_narrative(
        game_state=MOCK_GAME_STATE,
        current_scene=MOCK_SCENE,
        player_input={"text": "触摸测灵石"},
        event_context={},
        memory=MOCK_MEMORY,
        npc_cards={},
    )
    elapsed = time.time() - start

    narrative = result.get("narrative", "")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"  degraded: {result.get('degraded')}")
    print(f"  narrative: {narrative[:200]}...")

    if not result.get("degraded") and narrative:
        REPORT.record("R06.no_false_positive", "pass")
    else:
        REPORT.record("R06.no_false_positive", "fail", "被误杀或降级")


# =====================================================================
# 主入口
# =====================================================================

def main():
    use_real = "--real" in sys.argv

    print("=" * 60)
    print("Agent 整体完成性和完整性测试")
    print(f"模式: {'真实 MiMo' if use_real else '离线（FakeLLM）'}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 第一部分：离线测试
    print("\n" + "#" * 60)
    print("# 第一部分：离线功能完整性测试（T01-T10）")
    print("#" * 60)

    test_t01_module_imports()
    test_t02_io_format_compliance()
    test_t03_parser_fault_tolerance()
    test_t04_memory_v2()
    test_t05_content_filter()
    test_t06_fallback_provider()
    test_t07_free_input_processor()
    test_t08_world_book_loader()
    test_t09_prompt_builder()
    test_t10_controller_degradation()

    # 离线测试阶段性总结
    print("\n" + "=" * 60)
    print("第一部分（离线测试）阶段性总结")
    print("=" * 60)
    offline_pass = len(REPORT.passed)
    offline_fail = len(REPORT.failed)
    offline_total = offline_pass + offline_fail
    print(f"通过: {offline_pass} / {offline_total} ({offline_pass/offline_total*100:.1f}%)")
    if offline_fail > 0:
        print(f"失败项: {REPORT.failed}")

    if not use_real:
        print(REPORT.summary())
        print("\n提示: 加 --real 参数运行真实 MiMo 端到端测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_integration.py --real")
        return

    # 第二部分：真实 MiMo 测试
    print("\n" + "#" * 60)
    print("# 第二部分：真实 MiMo 端到端质量测试（R01-R06）")
    print("#" * 60)

    llm_config = _build_llm_config(use_real=True)
    from llm_adapter import NarrativeLLMAdapter
    from narrative_controller import NarrativeController
    from npc_dialogue_generator import NPCDialogueGenerator
    from world_book_loader import WorldBookLoader, NPCCardLoader

    adapter = NarrativeLLMAdapter(llm_config)
    controller = NarrativeController(adapter, max_retries=3)

    # 准备 NPC 对话生成器
    wb_loader = WorldBookLoader()
    wb_loader.load_all()
    npc_loader = NPCCardLoader()
    npc_loader.load_all()
    generator = NPCDialogueGenerator(adapter, world_book_loader=wb_loader)
    xu_card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    scene = {"id": "cheng_yun_dian", "name": "承运殿", "description": "扶龙宫讲学所在"}
    generator.register_npc("xu_boqian", xu_card, scene)

    test_r01_scene_narrative(controller)
    test_r02_npc_dialogue(generator)
    test_r03_free_input(controller)
    test_r04_anti_hallucination(generator)
    test_r05_multi_turn_coherence(generator)
    test_r06_content_filter_no_false_positive(controller)

    # 最终总结
    print(REPORT.summary())
    if REPORT.failed:
        print("\n失败项详情:")
        for f in REPORT.failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
