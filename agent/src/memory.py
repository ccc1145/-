"""记忆管理：短期对话窗口 + NPC 个体记忆。

策划书 5.2 节定义两类记忆：
- ShortTermMemory：保留最近 N 轮交互，直接注入 Prompt
- NPCMemory：每个 NPC 维护自己的对话历史，用于个性化对话生成

Day 4 实现基础版（两个类 + 统一管理器）；Day 9 增强：NPC 个体记忆优化。
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
    """NPC 个体记忆：每个 NPC 维护自己的对话历史。

    用于 NPC 动态对话生成（Day 9 启用），让 NPC "记得"之前和玩家说过什么。
    """

    def __init__(self, npc_id: str, max_history: int = 5) -> None:
        self.npc_id = npc_id
        self.max_history = max_history
        self.dialogues: list[dict[str, str]] = []

    def add_dialogue(self, player_text: str, npc_response: str) -> None:
        """添加一轮 NPC 对话记录。

        Args:
            player_text: 玩家说的话
            npc_response: NPC 的回应
        """
        self.dialogues.append({"player": player_text, "npc": npc_response})
        if len(self.dialogues) > self.max_history:
            self.dialogues.pop(0)

    def get_prompt_context(self) -> str:
        """格式化为 Prompt 中的对话历史文本。

        Returns:
            多行字符串，每轮对话占两行（玩家 / NPC）。
        """
        lines: list[str] = []
        for d in self.dialogues:
            lines.append(f"玩家：{d['player']}")
            lines.append(f"{self.npc_id}：{d['npc']}")
        return "\n".join(lines)

    def get_context(self) -> list[dict[str, str]]:
        """返回原始对话记录列表（结构化注入用）。"""
        return self.dialogues

    def clear(self) -> None:
        """清空该 NPC 的记忆。"""
        self.dialogues.clear()


class MemoryManager:
    """统一管理短期记忆 + 所有 NPC 的个体记忆。

    用法：
        manager = MemoryManager(max_turns=5, npc_max_history=5)
        manager.add_turn(turn=1, player_input="触摸测灵石", narrative="你将手...")
        manager.add_npc_dialogue("master", "拜见师父", "嗯，来了。")

        # 注入 Prompt
        memory_ctx = manager.get_prompt_context()
        # -> {"recent_events": [...], "dialogue_history": {...}}
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

    def add_npc_dialogue(self, npc_id: str, player_text: str, npc_response: str) -> None:
        """记录一轮 NPC 对话。"""
        if npc_id not in self._npc_memories:
            self._npc_memories[npc_id] = NPCMemory(
                npc_id=npc_id, max_history=self.npc_max_history
            )
        self._npc_memories[npc_id].add_dialogue(player_text, npc_response)

    def get_npc_memory(self, npc_id: str) -> NPCMemory | None:
        """获取指定 NPC 的记忆对象。"""
        return self._npc_memories.get(npc_id)

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
    # 自测
    print("=== ShortTermMemory 测试 ===")
    stm = ShortTermMemory(max_turns=3)
    for i in range(1, 5):  # 故意加 4 轮，验证窗口裁剪
        stm.add(turn=i, player_input=f"操作{i}", narrative=f"叙事{i}" * 50)
    ctx = stm.get_context()
    print(f"  窗口大小: {len(ctx)} (期望 3)")
    print(f"  最早轮次: {ctx[0]['turn']} (期望 2，因为第 1 轮被弹出)")
    print(f"  narrative 截断: {len(ctx[0]['narrative'])} 字符 (期望 200)")

    print("\n=== NPCMemory 测试 ===")
    npc_mem = NPCMemory(npc_id="master", max_history=2)
    npc_mem.add_dialogue("拜见师父", "嗯，来了。")
    npc_mem.add_dialogue("请教修炼", "心要静。")
    npc_mem.add_dialogue("再问一次", "已说过。")  # 第 1 轮应被弹出
    prompt_ctx = npc_mem.get_prompt_context()
    print(f"  对话轮数: {len(npc_mem.get_context())} (期望 2)")
    print(f"  Prompt 上下文:\n{prompt_ctx}")

    print("\n=== MemoryManager 测试 ===")
    manager = MemoryManager(max_turns=3, npc_max_history=3)
    manager.add_turn(turn=1, player_input="触摸测灵石", narrative="你将手放在测灵石上...")
    manager.add_npc_dialogue("master", "拜见师父", "嗯，来了。")
    ctx = manager.get_prompt_context()
    print(f"  recent_events: {len(ctx['recent_events'])} 条")
    print(f"  dialogue_history NPC 数: {len(ctx['dialogue_history'])}")
    print(f"  master 对话轮数: {len(ctx['dialogue_history']['master'])}")
