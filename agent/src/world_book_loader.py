"""世界观书 + NPC 角色卡加载器（Day 10 集成日）。

从 content/ 目录加载 MVP 交付物：
- content/world_books/*.json：11 本世界观书，共 147 条知识碎片
- content/npcs/*.yaml：39 个 NPC 角色卡（含 personality / knowledge / dialogue_examples）
- content/npc_pool/npc_pool.yaml：NPC 池（性格标签 / 背景经历 / 姓名池）

支持两类注入：
1. 静态注入：把全部世界观知识 / 某 NPC 的完整角色卡注入 Prompt（用于 system_prompt）
2. 关键词触发注入：根据玩家输入/对话内容/场景文本匹配 world_book 条目的 keys，
   只把命中的条目注入（节省 token，对齐 world_book.schema.json 的设计意图）

对齐文档：
- content/schema/world_book.schema.json：知识碎片结构（keys / content / category / weight / position）
- content/schema/npc.schema.json：NPC 角色卡结构（含 dialogue_examples / knowledge / relationships）
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 内容目录：xiuxian-simulator/content/
CONTENT_DIR = (
    Path(__file__).resolve().parent.parent.parent / "content"
)


class WorldBookLoader:
    """世界观书加载器：加载 content/world_books/*.json，支持关键词触发匹配。

    用法：
        loader = WorldBookLoader()
        loader.load_all()
        # 1. 静态注入（全部知识）
        all_entries = loader.get_all_entries()
        # 2. 关键词触发注入（只返回命中的条目）
        matched = loader.match("师父，弟子想请教修炼之法")
        # 3. 按类别获取
        rules = loader.get_entries_by_category("rule_knowledge")
    """

    def __init__(self, content_dir: Path | None = None) -> None:
        self._content_dir = content_dir or CONTENT_DIR
        self._books_dir = self._content_dir / "world_books"
        self._books: list[dict[str, Any]] = []
        self._entries: list[dict[str, Any]] = []
        self._loaded = False

    def load_all(self) -> None:
        """加载 world_books 目录下所有 .json 文件。"""
        if self._loaded:
            return
        if not self._books_dir.exists():
            logger.warning("world_books 目录不存在: %s", self._books_dir)
            return

        for book_path in sorted(self._books_dir.glob("*.json")):
            try:
                with open(book_path, encoding="utf-8") as f:
                    book = json.load(f)
                self._books.append(book)
                self._entries.extend(book.get("entries", []))
            except Exception as e:
                logger.error("加载 world_book 失败 %s: %s", book_path, e)

        self._loaded = True
        logger.info(
            "WorldBookLoader 已加载 %d 本书 / %d 条知识碎片",
            len(self._books),
            len(self._entries),
        )

    def get_all_entries(self) -> list[dict[str, Any]]:
        """返回所有条目（按 weight 降序）。"""
        self.load_all()
        return sorted(self._entries, key=lambda e: -e.get("weight", 100))

    def get_entries_by_category(self, category: str) -> list[dict[str, Any]]:
        """按 category 过滤条目。

        category 取值见 world_book.schema.json：
        world_lore / npc_lore / rule_knowledge / event_effect / location_info
        """
        self.load_all()
        return [
            e for e in self._entries if e.get("category") == category
        ]

    def match(
        self,
        text: str,
        *,
        recent_texts: list[str] | None = None,
        max_entries: int = 8,
    ) -> list[dict[str, Any]]:
        """关键词触发匹配：返回命中的条目列表。

        匹配规则（对齐 world_book.schema.json 的 keys + scan_depth）：
        - 检查 text + recent_texts（最近 N 条对话）中是否包含条目的任意 key
        - scan_depth 限制每个条目检查多少条 recent_texts（0=只检查当前输入）
        - 按 weight 降序排序，截断到 max_entries（避免 Prompt 过长）

        Args:
            text: 当前玩家输入或对话文本
            recent_texts: 最近 N 条对话历史（用于 scan_depth 检查）
            max_entries: 最多返回多少条命中条目
        """
        self.load_all()
        if not text and not recent_texts:
            return []

        recent_texts = recent_texts or []
        matched: list[dict[str, Any]] = []

        for entry in self._entries:
            keys = entry.get("keys", [])
            if not keys:
                continue

            scan_depth = entry.get("scan_depth", 4)
            # 构建待检查的文本列表：当前输入 + 最近 scan_depth 条历史
            texts_to_check = [text] + recent_texts[:scan_depth]
            combined = " ".join(texts_to_check)

            # any_key 逻辑：任意一个 key 命中即激活
            if any(key in combined for key in keys):
                matched.append(entry)

        # 按 weight 降序，截断
        matched.sort(key=lambda e: -e.get("weight", 100))
        return matched[:max_entries]

    def format_entries_for_prompt(self, entries: list[dict[str, Any]]) -> str:
        """把命中的条目格式化为 Prompt 文本。"""
        if not entries:
            return ""
        lines: list[str] = []
        for e in entries:
            name = e.get("name", e.get("entry_id", ""))
            content = e.get("content", "")
            category = e.get("category", "world_lore")
            lines.append(f"[{category}] {name}：{content}")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        """返回加载统计（调试用）。"""
        self.load_all()
        categories: dict[str, int] = {}
        for e in self._entries:
            cat = e.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "books": len(self._books),
            "entries": len(self._entries),
            "categories": categories,
        }


class NPCCardLoader:
    """NPC 角色卡加载器：加载 content/npcs/*.yaml。

    用法：
        loader = NPCCardLoader()
        loader.load_all()
        card = loader.get_npc("xu_boqian")  # 徐伯潜完整角色卡
        all_cards = loader.get_all_npcs()
    """

    def __init__(self, content_dir: Path | None = None) -> None:
        self._content_dir = content_dir or CONTENT_DIR
        self._npcs_dir = self._content_dir / "npcs"
        self._npcs: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def load_all(self) -> None:
        """加载 npcs 目录下所有 .yaml 文件。"""
        if self._loaded:
            return
        if not self._npcs_dir.exists():
            logger.warning("npcs 目录不存在: %s", self._npcs_dir)
            return

        for npc_path in sorted(self._npcs_dir.glob("*.yaml")):
            try:
                with open(npc_path, encoding="utf-8") as f:
                    npc = yaml.safe_load(f)
                if npc and "npc_id" in npc:
                    self._npcs[npc["npc_id"]] = npc
            except Exception as e:
                logger.error("加载 NPC 卡失败 %s: %s", npc_path, e)

        self._loaded = True
        logger.info("NPCCardLoader 已加载 %d 个 NPC 角色卡", len(self._npcs))

    def get_npc(self, npc_id: str) -> dict[str, Any] | None:
        """获取指定 NPC 的完整角色卡。"""
        self.load_all()
        return self._npcs.get(npc_id)

    def get_all_npcs(self) -> dict[str, dict[str, Any]]:
        """返回所有 NPC 角色卡（按 npc_id 索引）。"""
        self.load_all()
        return self._npcs

    def to_prompt_card(self, npc_id: str, current_affinity: int | None = None) -> dict[str, Any]:
        """把 NPC 卡转换为 Prompt Builder 期望的格式。

        NPC schema 字段：npc_id / name / description / personality / initial_state / knowledge /
                        dialogue_examples / relationships

        Prompt Builder 期望（对齐 npc_dialogue.j2）：
        - id / name / personality (traits/values/dislikes/speaking_style)
        - current_affinity（运行时状态）
        - description / knowledge / dialogue_examples（Day 10 新增，用于 Few-shot + 知识限制）
        """
        npc = self.get_npc(npc_id)
        if not npc:
            return {}

        affinity = (
            current_affinity
            if current_affinity is not None
            else npc.get("initial_state", {}).get("affinity", 0)
        )

        return {
            "id": npc.get("npc_id", npc_id),
            "name": npc.get("name", npc_id),
            "description": npc.get("description", ""),
            "personality": npc.get("personality", {}),
            "current_affinity": affinity,
            "location": npc.get("initial_state", {}).get("location", ""),
            "knowledge": npc.get("knowledge", []),
            "dialogue_examples": npc.get("dialogue_examples", []),
            "relationships": npc.get("relationships", []),
        }

    def stats(self) -> dict[str, Any]:
        """返回加载统计。"""
        self.load_all()
        return {"npcs": len(self._npcs), "ids": list(self._npcs.keys())}


if __name__ == "__main__":
    # 自测
    print("=" * 60)
    print("WorldBookLoader 自测")
    print("=" * 60)
    wb = WorldBookLoader()
    wb.load_all()
    stats = wb.stats()
    print(f"书数: {stats['books']}")
    print(f"条目数: {stats['entries']}")
    print(f"分类分布: {stats['categories']}")

    print("\n--- 关键词触发匹配测试 ---")
    test_cases = [
        "师父，弟子想请教修炼之法，该如何入门？",
        "玄清宗的门规是什么？",
        "灵根有几品？",
        "靖龙王李胤是怎么飞升的？",
    ]
    for text in test_cases:
        matched = wb.match(text)
        print(f"\n输入: {text}")
        print(f"命中 {len(matched)} 条:")
        for e in matched[:3]:
            print(f"  - [{e.get('category')}] {e.get('name')} (weight={e.get('weight')})")

    print("\n" + "=" * 60)
    print("NPCCardLoader 自测")
    print("=" * 60)
    npc_loader = NPCCardLoader()
    npc_loader.load_all()
    npc_stats = npc_loader.stats()
    print(f"NPC 数: {npc_stats['npcs']}")
    print(f"前 5 个 ID: {npc_stats['ids'][:5]}")

    print("\n--- 徐伯潜（xu_boqian）角色卡 ---")
    card = npc_loader.to_prompt_card("xu_boqian", current_affinity=15)
    print(f"姓名: {card['name']}")
    print(f"描述: {card['description'][:80]}...")
    print(f"性格特质: {card['personality'].get('traits')}")
    print(f"说话风格: {card['personality'].get('speaking_style')[:60]}...")
    print(f"知识条目: {len(card['knowledge'])} 条")
    print(f"对话示例: {len(card['dialogue_examples'])} 个（Few-shot）")
    print(f"关系: {len(card['relationships'])} 个")
    if card["dialogue_examples"]:
        ex = card["dialogue_examples"][1]  # 被问到靖王触发点
        print(f"\n示例对话（{ex.get('context')}）:")
        print(f"  玩家: {ex.get('user')}")
        print(f"  NPC : {ex.get('response')[:80]}...")
