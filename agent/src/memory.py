"""记忆管理 v2：短期对话窗口 + NPC 个体记忆（增强版）。

策划书 5.2 节定义两类记忆：
- ShortTermMemory：保留最近 N 轮交互，直接注入 Prompt
- NPCMemory：每个 NPC 维护自己的对话历史，用于个性化对话生成

Day 4 实现基础版（两个类 + 统一管理器）
Day 9 v2 增强：
  - NPCMemory 加入 key_events（关键事件记忆，不随窗口滚动）
  - 对话记录带 turn 时间戳
  - get_prompt_context 智能截断：历史过长时自动摘要
  - MemoryManager 新增 record_npc_event / get_npc_events 方法
"""
from __future__ import annotations

from typing import Any


class ShortTermMemory:
    """短期记忆：保留最近 N 轮交互，直接注入 Prompt。

    每轮交互记录：turn / player_input / narrative。
    narrative 截断到 200 字，避免 Prompt 过长。
    """

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns = max_turns
        self.history: list[dict[str, Any]] = []

    def add(self, turn: int, player_input: str, narrative: str) -> None:
        """添加一轮交互记录。

        Args:
            turn: 回合数
            player_input: 玩家输入文本
            narrative: 本轮叙事文本（自动截断到 200 字）
        """
        self.history.append(
            {
                "turn": turn,
                "player_input": player_input,
                "narrative": narrative[:200] if narrative else "",
            }
        )
        # 超出窗口：弹出最老的
        if len(self.history) > self.max_turns:
            self.history.pop(0)

    def get_context(self) -> list[dict[str, Any]]:
        """返回当前窗口内的所有交互记录（注入 Prompt 用）。"""
        return self.history

    def clear(self) -> None:
        """清空记忆（新游戏/读档时调用）。"""
        self.history.clear()


class NPCMemory:
    """NPC 个体记忆 v2：对话历史 + 关键事件记忆。

    v2 增强：
    - 对话记录带 turn 时间戳，让 NPC 知道"上次聊是在第几轮"
    - 新增 key_events 列表：记录关键事件（如玩家帮过 NPC / 得罪过 NPC），
      这些记忆不随对话窗口滚动而丢失，长期影响 NPC 态度
    - get_prompt_context 智能截断：历史超过 3 轮时自动生成摘要
    """

    def __init__(self, npc_id: str, max_history: int = 5) -> None:
        self.npc_id = npc_id
        self.max_history = max_history
        self.dialogues: list[dict[str, Any]] = []  # v2: 带 turn
        self.key_events: list[dict[str, Any]] = []  # v2 新增：关键事件

    def add_dialogue(
        self, player_text: str, npc_response: str, turn: int = 0
    ) -> None:
        """添加一轮 NPC 对话记录。

        Args:
            player_text: 玩家说的话
            npc_response: NPC 的回应
            turn: 当前游戏回合数（v2 新增，用于时间感知）
        """
        self.dialogues.append(
            {
                "turn": turn,
                "player": player_text,
                "npc": npc_response,
            }
        )
        if len(self.dialogues) > self.max_history:
            self.dialogues.pop(0)

    def record_event(
        self, event_type: str, description: str, turn: int = 0, impact: int = 0
    ) -> None:
        """记录关键事件（v2 新增）。

        关键事件不随对话窗口滚动而丢失，长期影响 NPC 对玩家的态度。

        Args:
            event_type: 事件类型，如 "helped" / "offended" / "gift" / "promise"
            description: 事件描述，如 "玩家在试炼中帮玄清真人解围"
            turn: 发生回合
            impact: 对好感度的影响（正/负），用于后续 NPC 态度参考
        """
        self.key_events.append(
            {
                "type": event_type,
                "description": description,
                "turn": turn,
                "impact": impact,
            }
        )

    def get_prompt_context(self) -> str:
        """格式化为 Prompt 中的对话历史文本（v2 增强智能截断）。

        策略：
        - 历史 ≤ 3 轮：完整列出
        - 历史 > 3 轮：摘要 + 最近 2 轮详情
        - 有关键事件：在顶部列出（让 NPC 记得玩家做过什么）
        """
        lines: list[str] = []

        # 关键事件（长期记忆，始终展示）
        if self.key_events:
            lines.append("【关键记忆】")
            for ev in self.key_events[-3:]:  # 最近 3 个关键事件
                lines.append(f"  - 第{ev['turn']}轮 {ev['description']}")
            lines.append("")

        # 对话历史
        lines.append("【近期对话】")
        if len(self.dialogues) <= 3:
            for d in self.dialogues:
                lines.append(f"  第{d['turn']}轮 玩家：{d['player']}")
                lines.append(f"  第{d['turn']}轮 {self.npc_id}：{d['npc']}")
        else:
            # 摘要 + 最近 2 轮
            total = len(self.dialogues)
            lines.append(f"  （此前已对话 {total} 轮，省略早期内容）")
            for d in self.dialogues[-2:]:
                lines.append(f"  第{d['turn']}轮 玩家：{d['player']}")
                lines.append(f"  第{d['turn']}轮 {self.npc_id}：{d['npc']}")

        if not self.dialogues:
            lines.append("  （初次对话，无历史）")

        return "\n".join(lines)

    def get_context(self) -> list[dict[str, Any]]:
        """返回原始对话记录列表（结构化注入用）。"""
        return self.dialogues

    def get_events(self) -> list[dict[str, Any]]:
        """返回关键事件列表（v2 新增）。"""
        return self.key_events

    def clear(self) -> None:
        """清空该 NPC 的所有记忆（对话 + 事件）。"""
        self.dialogues.clear()
        self.key_events.clear()


class MemoryManager:
    """统一管理短期记忆 + 所有 NPC 的个体记忆（v2）。

    v2 新增方法：
    - record_npc_event: 记录 NPC 关键事件
    - get_npc_events: 获取 NPC 关键事件

    用法：
        manager = MemoryManager(max_turns=5, npc_max_history=5)
        manager.add_turn(turn=1, player_input="触摸测灵石", narrative="你将手...")
        manager.add_npc_dialogue("master", "拜见师父", "嗯，来了。", turn=1)
        manager.record_npc_event("master", "helped", "玩家帮玄清真人解围", turn=3, impact=10)

        # 注入 Prompt
        memory_ctx = manager.get_prompt_context()
    """

    def __init__(
        self, max_turns: int = 5, npc_max_history: int = 5
    ) -> None:
        self.short_term = ShortTermMemory(max_turns=max_turns)
        self.npc_max_history = npc_max_history
        self._npc_memories: dict[str, NPCMemory] = {}

    def add_turn(self, turn: int, player_input: str, narrative: str) -> None:
        """记录一轮游戏交互。"""
        self.short_term.add(turn, player_input, narrative)

    def add_npc_dialogue(
        self, npc_id: str, player_text: str, npc_response: str, turn: int = 0
    ) -> None:
        """记录一轮 NPC 对话（v2: 带 turn）。"""
        if npc_id not in self._npc_memories:
            self._npc_memories[npc_id] = NPCMemory(
                npc_id=npc_id, max_history=self.npc_max_history
            )
        self._npc_memories[npc_id].add_dialogue(player_text, npc_response, turn=turn)

    def record_npc_event(
        self,
        npc_id: str,
        event_type: str,
        description: str,
        turn: int = 0,
        impact: int = 0,
    ) -> None:
        """记录 NPC 关键事件（v2 新增）。

        Args:
            npc_id: NPC ID
            event_type: 事件类型（helped/offended/gift/promise 等）
            description: 事件描述
            turn: 发生回合
            impact: 对好感度的影响
        """
        if npc_id not in self._npc_memories:
            self._npc_memories[npc_id] = NPCMemory(
                npc_id=npc_id, max_history=self.npc_max_history
            )
        self._npc_memories[npc_id].record_event(
            event_type=event_type,
            description=description,
            turn=turn,
            impact=impact,
        )

    def get_npc_memory(self, npc_id: str) -> NPCMemory | None:
        """获取指定 NPC 的记忆对象。"""
        return self._npc_memories.get(npc_id)

    def get_npc_events(self, npc_id: str) -> list[dict[str, Any]]:
        """获取指定 NPC 的关键事件列表（v2 新增）。"""
        memory = self._npc_memories.get(npc_id)
        return memory.get_events() if memory else []

    def get_prompt_context(self) -> dict[str, Any]:
        """返回注入 Prompt 的记忆上下文。

        对齐 docs/agent-io-format.md 第 2.6 节 memory 结构：
        - recent_events: 最近 N 轮交互
        - dialogue_history: 各 NPC 的对话历史
        """
        return {
            "recent_events": self.short_term.get_context(),
            "dialogue_history": {
                npc_id: memory.get_context()
                for npc_id, memory in self._npc_memories.items()
            },
        }

    def clear(self) -> None:
        """清空所有记忆（新游戏/读档时调用）。"""
        self.short_term.clear()
        self._npc_memories.clear()


if __name__ == "__main__":
    # 自测 v2
    print("=== ShortTermMemory 测试 ===")
    stm = ShortTermMemory(max_turns=3)
    for i in range(1, 5):  # 故意加 4 轮，验证窗口裁剪
        stm.add(turn=i, player_input=f"操作{i}", narrative=f"叙事{i}" * 50)
    ctx = stm.get_context()
    print(f"  窗口大小: {len(ctx)} (期望 3)")
    print(f"  最早轮次: {ctx[0]['turn']} (期望 2，因为第 1 轮被弹出)")
    print(f"  narrative 截断: {len(ctx[0]['narrative'])} 字符 (期望 200)")

    print("\n=== NPCMemory v2 测试 ===")
    npc_mem = NPCMemory(npc_id="master", max_history=3)
    # 记录关键事件
    npc_mem.record_event("helped", "玩家在试炼中帮玄清真人解围", turn=3, impact=10)
    # 对话历史
    npc_mem.add_dialogue("拜见师父", "嗯，来了。", turn=1)
    npc_mem.add_dialogue("请教修炼", "心要静。", turn=2)
    npc_mem.add_dialogue("再问一次", "已说过。", turn=4)
    print(f"  对话轮数: {len(npc_mem.get_context())} (期望 3)")
    print(f"  关键事件数: {len(npc_mem.get_events())} (期望 1)")
    print(f"  Prompt 上下文:\n{npc_mem.get_prompt_context()}")

    print("\n=== NPCMemory 智能截断测试（>3 轮触发摘要）===")
    npc_mem2 = NPCMemory(npc_id="senior", max_history=5)
    for i in range(1, 6):
        npc_mem2.add_dialogue(f"问题{i}", f"回答{i}", turn=i)
    print(f"  对话轮数: {len(npc_mem2.get_context())} (期望 5)")
    print(f"  Prompt 上下文（应含摘要）:\n{npc_mem2.get_prompt_context()}")

    print("\n=== MemoryManager v2 测试 ===")
    manager = MemoryManager(max_turns=3, npc_max_history=3)
    manager.add_turn(turn=1, player_input="触摸测灵石", narrative="你将手放在测灵石上...")
    manager.add_npc_dialogue("master", "拜见师父", "嗯，来了。", turn=1)
    manager.record_npc_event("master", "helped", "玩家帮师父解围", turn=3, impact=10)
    ctx = manager.get_prompt_context()
    print(f"  recent_events: {len(ctx['recent_events'])} 条")
    print(f"  dialogue_history NPC 数: {len(ctx['dialogue_history'])}")
    print(f"  master 对话轮数: {len(ctx['dialogue_history']['master'])}")
    print(f"  master 关键事件数: {len(manager.get_npc_events('master'))} (期望 1)")

