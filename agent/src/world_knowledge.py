"""MVP 世界观知识库（硬编码临时版）。

策划书 Day 5 任务 2：注入世界观知识到 Prompt。
人员D 的 content/world/ 尚未产出，先用硬编码版本跑通端到端流程。
Day 10 替换为从 content/world/*.md 加载。

知识分三类，对齐 docs/agent-io-format.md 第 2.6 节 world_knowledge 字段：
- 修仙体系：境界划分、灵根、修炼常识
- 门派设定：青云门背景、关键人物
- 地理常识：游戏内出现的地点
"""
from __future__ import annotations


# 修仙体系知识
CULTIVATION_KNOWLEDGE: list[str] = [
    "修仙第一步是练气，将天地灵气引入体内，淬炼经脉。",
    "练气期共九层，每突破一层修为增长一阶。九层圆满后方可冲击筑基。",
    "筑基期是正式踏入修仙之门的标志，寿元可达两百载。",
    "灵根是修仙的天赋根基，分金木水火土五行。灵根品质分一到九等，一等最劣，九等最优。",
    "单灵根（天灵根）修炼速度最快，多灵根次之，无灵根者无法修仙。",
    "灵石是修仙界通用货币，分下品/中品/上品/极品四等。",
]

# 门派设定知识
SECT_KNOWLEDGE: list[str] = [
    "青云门建派三百年，是修仙界四大宗门之一，以剑道和丹道闻名。",
    "青云门坐落于青云山主峰，山上有聚灵阵护持，灵气浓郁。",
    "青云门掌门玄清真人，筑基后期修为，性格严厉但护短。",
    "青云门弟子分外门弟子和内门弟子，内门弟子可直接受长老指导。",
    "入门试炼通过测灵石检测灵根，灵根品质达标者方可入门。",
]

# 地理常识
GEOGRAPHY_KNOWLEDGE: list[str] = [
    "青云山位于修仙界东域，山势险峻，终年云雾缭绕。",
    "试炼场位于青云山半山腰，是入门弟子测灵根之地。",
    "藏经阁在主峰之巅，收藏青云门三百年来的功法典籍。",
    "丹房在后山，由丹道长老主持，炼制各类丹药。",
]

# 修炼常识（动作相关）
ACTION_KNOWLEDGE: list[str] = [
    "打坐修炼是最基础的积累修为方式，需在灵气浓郁处进行。",
    "服食丹药可快速提升修为，但有走火入魔风险。",
    "突破境界需要足够修为积累，贸然突破会导致经脉受损。",
    "悟道是高阶修士的提升方式，需机缘巧合。",
]


def get_all_world_knowledge() -> list[str]:
    """返回全部世界观知识点（注入 Prompt 用）。

    Day 10 后改为从 content/world/*.md 动态加载。
    """
    return (
        CULTIVATION_KNOWLEDGE
        + SECT_KNOWLEDGE
        + GEOGRAPHY_KNOWLEDGE
        + ACTION_KNOWLEDGE
    )


def get_knowledge_by_category(category: str) -> list[str]:
    """按类别获取知识点。

    Args:
        category: "cultivation" / "sect" / "geography" / "action"
    """
    mapping = {
        "cultivation": CULTIVATION_KNOWLEDGE,
        "sect": SECT_KNOWLEDGE,
        "geography": GEOGRAPHY_KNOWLEDGE,
        "action": ACTION_KNOWLEDGE,
    }
    return mapping.get(category, [])


# 各场景的预设降级文案（Day 12 降级机制用，这里先硬编码）
SCENE_PRESET_NARRATIVES: dict[str, str] = {
    "trial_grounds": "你站在试炼场中央，面前的测灵石古朴沧桑，仿佛在等待你的触碰。周围的师兄师姐投来或期待或审视的目光。",
    "trial_result": "测灵石的光芒渐渐消散，你的灵根属性已明。无论结果如何，修仙之路才刚刚开始。",
    "sect_entrance": "你踏入青云门的山门，迎面而来的是古朴的青石长阶，两侧松柏苍翠，灵气沁人心脾。",
    "default": "你继续前行，前路漫漫，修仙之道在乎一心。",
}


def get_preset_narrative(scene_id: str) -> str:
    """获取场景预设降级文案。"""
    return SCENE_PRESET_NARRATIVES.get(scene_id, SCENE_PRESET_NARRATIVES["default"])


if __name__ == "__main__":
    # 自测
    all_knowledge = get_all_world_knowledge()
    print(f"知识点总数: {len(all_knowledge)}")
    for cat in ("cultivation", "sect", "geography", "action"):
        print(f"  {cat}: {len(get_knowledge_by_category(cat))} 条")
    print(f"\n预设降级文案场景数: {len(SCENE_PRESET_NARRATIVES)}")
    print(f"trial_grounds 预设: {get_preset_narrative('trial_grounds')[:30]}...")
