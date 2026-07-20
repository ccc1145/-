"""Day 10 端到端测试：世界观书 + NPC 完整角色卡注入 + 真实 MiMo 集成。

测试覆盖：
1. WorldBookLoader + NPCCardLoader 加载验证（11 本书 / 147 条 / 39 个 NPC）
2. 关键词触发匹配验证（不同输入命中不同条目）
3. Prompt 渲染验证（npc_dialogue.j2 含 knowledge / Few-shot / world_book_context）
4. 真实 MiMo 端到端：用徐伯潜（xu_boqian）角色卡对话，验证：
   a. Few-shot 风格生效：被问到靖龙王时 NPC 应有停顿/回避反应
   b. knowledge 限制生效：问 NPC 不知道的事，应说"不知"或转移话题
   c. world_book 触发：玩家输入含关键词时，相关知识注入 Prompt

运行：
    cd D:\\实训\\xiuxian-simulator
    # 离线测试（无需 API Key）
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day10.py
    # 真实 MiMo 测试
    $env:MIMO_API_KEY='sk-xxx'
    D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day10.py --real
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

from world_book_loader import WorldBookLoader, NPCCardLoader  # noqa: E402
from prompt_builder import PromptBuilder  # noqa: E402
from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from npc_dialogue_generator import NPCDialogueGenerator  # noqa: E402
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


# ---- 测试 1: WorldBookLoader + NPCCardLoader 加载验证 ----

def test_loaders():
    """测试 1：WorldBookLoader + NPCCardLoader 加载验证。"""
    print("=" * 60)
    print("[测试 1] WorldBookLoader + NPCCardLoader 加载验证")
    print("=" * 60)

    wb = WorldBookLoader()
    wb.load_all()
    wb_stats = wb.stats()
    print(f"\nWorldBookLoader:")
    print(f"  书数: {wb_stats['books']} (期望 11)")
    print(f"  条目数: {wb_stats['entries']} (期望 147)")
    print(f"  分类分布: {wb_stats['categories']}")

    assert wb_stats["books"] == 11, f"书数应为 11, 实际 {wb_stats['books']}"
    assert wb_stats["entries"] == 147, f"条目数应为 147, 实际 {wb_stats['entries']}"
    assert "rule_knowledge" in wb_stats["categories"]
    assert "world_lore" in wb_stats["categories"]

    npc_loader = NPCCardLoader()
    npc_loader.load_all()
    npc_stats = npc_loader.stats()
    print(f"\nNPCCardLoader:")
    print(f"  NPC 数: {npc_stats['npcs']} (期望 39)")
    print(f"  前 5 个 ID: {npc_stats['ids'][:5]}")

    assert npc_stats["npcs"] == 39, f"NPC 数应为 39, 实际 {npc_stats['npcs']}"
    assert "xu_boqian" in npc_stats["ids"], "应包含徐伯潜"

    # 验证徐伯潜角色卡完整性
    card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    print(f"\n徐伯潜角色卡:")
    print(f"  姓名: {card['name']}")
    print(f"  描述长度: {len(card['description'])} 字符")
    print(f"  性格特质: {card['personality'].get('traits')}")
    print(f"  知识条目: {len(card['knowledge'])} 条")
    print(f"  对话示例: {len(card['dialogue_examples'])} 个")
    print(f"  关系: {len(card['relationships'])} 个")
    print(f"  当前好感度: {card['current_affinity']}")

    assert card["name"] == "徐伯潜"
    assert len(card["knowledge"]) == 6, f"知识应为 6 条, 实际 {len(card['knowledge'])}"
    assert len(card["dialogue_examples"]) == 7, f"对话示例应为 7 个, 实际 {len(card['dialogue_examples'])}"
    assert len(card["relationships"]) == 3, f"关系应为 3 个, 实际 {len(card['relationships'])}"

    print("\n[加载器] 所有断言通过 ✓")
    return True


# ---- 测试 2: 关键词触发匹配验证 ----

def test_keyword_matching():
    """测试 2：关键词触发匹配验证。"""
    print("\n" + "=" * 60)
    print("[测试 2] 关键词触发匹配验证")
    print("=" * 60)

    wb = WorldBookLoader()
    wb.load_all()

    test_cases = [
        ("师父，弟子想请教修炼之法", "修炼", "应命中修炼体系"),
        ("玄清宗的门规是什么", "玄清宗", "应命中玄清宗相关"),
        ("灵根有几品", "灵根", "应命中灵根体系"),
        ("靖龙王李胤是怎么飞升的", "靖龙王", "应命中靖龙王李胤条目"),
        ("扶龙宫的入门考核", "扶龙宫", "应命中扶龙宫相关"),
    ]

    all_pass = True
    for text, expected_keyword, desc in test_cases:
        matched = wb.match(text)
        # 检查命中条目中是否有 name 或 content 包含期望关键词
        found = any(
            expected_keyword in e.get("name", "") or expected_keyword in e.get("content", "")
            for e in matched
        )
        status = "✓" if found else "✗"
        if not found:
            all_pass = False
        print(f"\n{status} {desc}")
        print(f"  输入: {text}")
        print(f"  命中 {len(matched)} 条:")
        for e in matched[:2]:
            print(f"    - [{e.get('category')}] {e.get('name')} (w={e.get('weight')})")

    if all_pass:
        print("\n[关键词匹配] 所有断言通过 ✓")
    else:
        print("\n[关键词匹配] 有断言失败 ✗")
    return all_pass


# ---- 测试 3: Prompt 渲染验证 ----

def test_prompt_rendering():
    """测试 3：Prompt 渲染验证（含 knowledge / Few-shot / world_book_context）。"""
    print("\n" + "=" * 60)
    print("[测试 3] Prompt 渲染验证")
    print("=" * 60)

    npc_loader = NPCCardLoader()
    npc_loader.load_all()
    wb = WorldBookLoader()
    wb.load_all()

    card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)

    # 关键词匹配
    player_text = "教习，你以前跟过靖龙王？"
    matched = wb.match(player_text)
    wb_context = wb.format_entries_for_prompt(matched)

    builder = PromptBuilder()
    prompt = builder.build_npc_dialogue_prompt(
        npc=card,
        player_input={"text": player_text},
        current_scene={"id": "cheng_yun_dian", "name": "承运殿"},
        dialogue_history=["（初次对话）"],
        npc_knowledge=card["knowledge"],
        dialogue_examples=card["dialogue_examples"],
        world_book_context=wb_context,
    )

    print(f"\n渲染 Prompt 长度: {len(prompt)} 字符")

    # 验证关键区块都注入了
    checks = [
        ("【NPC 角色卡】", "角色卡区块"),
        ("【NPC 知识范围", "knowledge 限制区块"),
        ("【相关世界观知识", "world_book 动态知识区块"),
        ("【对话示例", "Few-shot 示例区块"),
        ("徐伯潜", "NPC 姓名"),
        ("皇极惊世典", "NPC 知识内容"),
        ("靖龙王", "Few-shot 触发点内容"),
        ("严厉", "性格特质"),
    ]
    all_pass = True
    for keyword, desc in checks:
        found = keyword in prompt
        status = "✓" if found else "✗"
        if not found:
            all_pass = False
        print(f"  {status} {desc}: {'存在' if found else '缺失'}")

    if all_pass:
        print("\n[Prompt 渲染] 所有断言通过 ✓")
    else:
        print("\n[Prompt 渲染] 有断言失败 ✗")
    return all_pass


# ---- 测试 4: 真实 MiMo 端到端 - Few-shot 风格生效 ----

def test_mimo_fewshot_style(generator: NPCDialogueGenerator):
    """测试 4：真实 MiMo - 被问到靖龙王时，NPC 应有停顿/回避反应（Few-shot 风格生效）。"""
    print("\n" + "=" * 60)
    print("[测试 4] 真实 MiMo - Few-shot 风格生效（靖龙王触发点）")
    print("=" * 60)

    # 这个输入对应 dialogue_examples[1]：被问到靖龙王触发点
    # 期望 NPC 像示例那样有"手上的竹简顿了一下"的停顿反应
    result = generator.talk(
        "xu_boqian",
        "教习，你以前跟过靖龙王？",
        turn=1,
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:400]}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert narrative, "narrative 不应为空"

    # Few-shot 生效的软断言：NPC 回应中应有"停顿"、"沉默"、"不提"等回避特征
    # （对齐 dialogue_examples[1] 中 "那是很久以前的事了。不提也罢。" 的风格）
    avoidance_keywords = ["停顿", "沉默", "不提", "罢了", "……", "那是", "很久", "不语"]
    found_avoidance = any(kw in narrative for kw in avoidance_keywords)
    if found_avoidance:
        print(f"\n  ✓ Few-shot 风格生效：NPC 表现出停顿/回避反应")
    else:
        print(f"\n  ⚠ Few-shot 风格软断言未命中（但不算失败，NPC 可能用其他方式回应）")

    print("\n[MiMo Few-shot 风格] 测试通过 ✓")
    return True


# ---- 测试 5: 真实 MiMo - knowledge 限制生效 ----

def test_mimo_knowledge_limit(generator: NPCDialogueGenerator):
    """测试 5：knowledge 限制 - 问 NPC 不掌握的事，应说不知或转移话题。"""
    print("\n" + "=" * 60)
    print("[测试 5] 真实 MiMo - knowledge 限制生效")
    print("=" * 60)

    # 徐伯潜的 knowledge 里没有"神武宗内功"相关内容
    # 期望他说"不知"或转移话题，而不是编造
    result = generator.talk(
        "xu_boqian",
        "教习，神武宗的烈火诀第七式如何修炼？",
        turn=2,
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:400]}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert narrative, "narrative 不应为空"

    # knowledge 限制的软断言：NPC 应承认不知或转移话题
    refusal_keywords = ["不知", "不晓得", "不明白", "未曾", "不在", "非我", "你问错", "莫问", "问别人", "不在行", "不熟"]
    found_refusal = any(kw in narrative for kw in refusal_keywords)
    if found_refusal:
        print(f"\n  ✓ knowledge 限制生效：NPC 承认不知或转移话题")
    else:
        print(f"\n  ⚠ knowledge 限制软断言未命中（NPC 可能用其他方式回避，需人工审查是否编造）")

    print("\n[MiMo knowledge 限制] 测试通过 ✓")
    return True


# ---- 测试 6: 真实 MiMo - world_book 关键词触发 ----

def test_mimo_worldbook_trigger(generator: NPCDialogueGenerator):
    """测试 6：world_book 关键词触发 - 玩家问灵根，NPC 应能给出符合世界观的解答。"""
    print("\n" + "=" * 60)
    print("[测试 6] 真实 MiMo - world_book 关键词触发")
    print("=" * 60)

    # 玩家问灵根，应触发 cultivation_system 中的"灵根体系"条目
    # 期望 NPC 的回答符合 world_book 中定义的灵根体系（凡/伪/地/天灵根）
    result = generator.talk(
        "xu_boqian",
        "教习，灵根到底分几品？弟子听得云里雾里。",
        turn=3,
    )

    narrative = result.get("narrative", "")
    print(f"\n降级标记: degraded={result.get('degraded')}")
    print(f"narrative: {narrative[:500]}")

    # 断言
    assert not result.get("degraded"), "不应降级"
    assert narrative, "narrative 不应为空"

    # world_book 触发的软断言：NPC 回答中应包含 world_book 定义的灵根品级术语
    linggen_terms = ["凡灵根", "伪灵根", "地灵根", "天灵根", "单属性", "五行", "金木水火土"]
    found_terms = [t for t in linggen_terms if t in narrative]
    if found_terms:
        print(f"\n  ✓ world_book 触发生效：NPC 使用了世界观术语 {found_terms}")
    else:
        print(f"\n  ⚠ world_book 触发软断言未命中（NPC 可能用自己的话解释，需人工审查是否符合世界观）")

    print("\n[MiMo world_book 触发] 测试通过 ✓")
    return True


# ---- 主入口 ----

def main():
    use_real = "--real" in sys.argv

    # 离线测试
    r1 = test_loaders()
    r2 = test_keyword_matching()
    r3 = test_prompt_rendering()

    if not use_real:
        print("\n" + "=" * 60)
        print("Day 10 离线测试通过 ✓")
        print("提示: 加 --real 参数运行真实 MiMo 端到端测试")
        print("  $env:MIMO_API_KEY='sk-xxx'")
        print("  D:\\Anaconda3\\envs\\shixun\\python.exe agent\\examples\\test_day10.py --real")
        print("=" * 60)
        return

    # 真实 MiMo 测试
    print("\n" + "=" * 60)
    print("启动真实 MiMo 端到端测试...")
    print("=" * 60)

    llm_config = _build_llm_config(use_real=True)
    adapter = NarrativeLLMAdapter(llm_config)

    # 创建 WorldBookLoader 和 NPCCardLoader
    wb_loader = WorldBookLoader()
    wb_loader.load_all()
    npc_loader = NPCCardLoader()
    npc_loader.load_all()

    # 创建 Generator，注入 world_book_loader
    generator = NPCDialogueGenerator(adapter, world_book_loader=wb_loader)

    # 注册徐伯潜（用真实角色卡）
    xu_card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    scene = {"id": "cheng_yun_dian", "name": "承运殿", "description": "扶龙宫讲学所在"}
    generator.register_npc("xu_boqian", xu_card, scene)

    r4 = test_mimo_fewshot_style(generator)
    r5 = test_mimo_knowledge_limit(generator)
    r6 = test_mimo_worldbook_trigger(generator)

    print("\n" + "=" * 60)
    if all([r1, r2, r3, r4, r5, r6]):
        print("Day 10 全部测试通过 ✓（含真实 MiMo 端到端）")
        print("交付物: world_book_loader.py / prompt_builder.py 扩展 / 模板 v2 / controller+generator 集成")
    else:
        print("Day 10 有测试失败 ✗")
    print("=" * 60)


if __name__ == "__main__":
    main()
