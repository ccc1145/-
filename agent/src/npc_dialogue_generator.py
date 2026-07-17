"""NPC 对话生成器：封装多 NPC 对话生成 + 记忆驱动的连贯性。

策划书 Day 9 任务：实现 npc_dialogue_generator.py（NPC 动态对话生成）。

与 NarrativeController.generate_npc_dialogue 的区别：
- NarrativeController 是通用调度器，对话只是其一种 request_type
- NPCDialogueGenerator 专注对话场景，提供：
  1. 多 NPC 管理（注册/切换当前对话 NPC）
  2. 集成 MemoryManager v2（记忆驱动连贯性）
  3. 自动记录对话到记忆（生成后自动 add_npc_dialogue）
  4. 基于关键事件影响 NPC 态度（如玩家帮过 NPC，NPC 更热情）

用法：
    generator = NPCDialogueGenerator(llm_adapter, memory_manager)
    generator.register_npc("master", master_card, current_scene)
    result = generator.talk("master", "师父，弟子想请教修炼之法", turn=3)
    # 对话自动记录到 memory_manager，下次对话 NPC 能"记得"
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from memory import MemoryManager
from prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from llm_adapter import NarrativeLLMAdapter
    from narrative_controller import NarrativeController

logger = logging.getLogger(__name__)


class NPCDialogueGenerator:
    """NPC 对话生成器：多 NPC 管理 + 记忆驱动连贯性。

    核心能力：
    1. register_npc: 注册 NPC（角色卡 + 所在场景）
    2. talk: 与指定 NPC 对话，自动记录到记忆
    3. 对话生成委托给 NarrativeController（复用重试+降级机制）
    4. 生成后自动调用 memory_manager.add_npc_dialogue
    """

    def __init__(
        self,
        llm_adapter: "NarrativeLLMAdapter",
        memory_manager: MemoryManager | None = None,
        controller: "NarrativeController | None" = None,
    ) -> None:
        """
        Args:
            llm_adapter: LLM 适配器
            memory_manager: 记忆管理器（可选，不传则内部创建）
            controller: NarrativeController（可选，不传则内部创建）
        """
        self._llm = llm_adapter
        self._memory = memory_manager or MemoryManager()
        self._prompt_builder = PromptBuilder()
        # 延迟导入避免循环依赖
        if controller is not None:
            self._controller = controller
        else:
            from narrative_controller import NarrativeController
            self._controller = NarrativeController(llm_adapter)
        # 注册的 NPC：{npc_id: {"card": ..., "scene": ...}}
        self._npcs: dict[str, dict[str, Any]] = {}

    # ---- NPC 管理 ----

    def register_npc(
        self,
        npc_id: str,
        npc_card: dict[str, Any],
        current_scene: dict[str, Any],
    ) -> None:
        """注册一个 NPC，后续可用 talk(npc_id, ...) 与其对话。

        Args:
            npc_id: NPC ID（如 "master"）
            npc_card: NPC 角色卡，需含 name / personality / current_affinity
            current_scene: NPC 所在场景
        """
        self._npcs[npc_id] = {"card": npc_card, "scene": current_scene}
        logger.info("注册 NPC: %s (%s)", npc_id, npc_card.get("name", ""))

    def update_npc_card(self, npc_id: str, npc_card: dict[str, Any]) -> None:
        """更新已注册 NPC 的角色卡（如好感度变化后）。"""
        if npc_id in self._npcs:
            self._npcs[npc_id]["card"] = npc_card

    def update_scene(self, npc_id: str, scene: dict[str, Any]) -> None:
        """更新 NPC 所在场景（玩家移动到新场景时）。"""
        if npc_id in self._npcs:
            self._npcs[npc_id]["scene"] = scene

    # ---- 对话生成 ----

    def talk(
        self,
        npc_id: str,
        player_text: str,
        *,
        turn: int = 0,
        npc_card_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """与指定 NPC 对话。

        流程：
        1. 查找已注册的 NPC 角色卡和场景
        2. 从 MemoryManager 获取该 NPC 的对话历史
        3. 委托 NarrativeController 生成对话
        4. 自动记录到 MemoryManager（带 turn）

        Args:
            npc_id: NPC ID
            player_text: 玩家说的话
            turn: 当前游戏回合数（记录到记忆）
            npc_card_override: 临时覆盖角色卡（如好感度临时变化）

        Returns:
            符合 docs/agent-io-format.md 的对话输出 dict
        """
        if npc_id not in self._npcs:
            raise ValueError(f"NPC {npc_id} 未注册，请先调用 register_npc")

        npc_data = self._npcs[npc_id]
        npc_card = npc_card_override or npc_data["card"]
        scene = npc_data["scene"]

        # 获取该 NPC 的对话历史（用 v2 智能截断后的文本）
        npc_memory = self._memory.get_npc_memory(npc_id)
        dialogue_history_lines: list[str] = []
        if npc_memory:
            # get_prompt_context 返回格式化文本，拆成行给模板
            dialogue_history_lines = npc_memory.get_prompt_context().split("\n")

        # 委托 controller 生成
        result = self._controller.generate_npc_dialogue(
            npc=npc_card,
            player_input={"text": player_text},
            current_scene=scene,
            dialogue_history=dialogue_history_lines,
        )

        # 提取 NPC 回应文本，记录到记忆
        npc_response = self._extract_npc_response(result)
        if npc_response:
            self._memory.add_npc_dialogue(
                npc_id=npc_id,
                player_text=player_text,
                npc_response=npc_response,
                turn=turn,
            )
            logger.info(
                "记录对话到记忆: npc=%s, turn=%d, player=%s...",
                npc_id, turn, player_text[:20],
            )

        return result

    def record_event(
        self,
        npc_id: str,
        event_type: str,
        description: str,
        turn: int = 0,
        impact: int = 0,
    ) -> None:
        """记录 NPC 关键事件（委托给 MemoryManager）。

        例：玩家帮玄清真人解围 → record_event("master", "helped", "...", turn=5, impact=10)
        后续对话时，NPC 会"记得"这件事，态度更热情。
        """
        self._memory.record_npc_event(
            npc_id=npc_id,
            event_type=event_type,
            description=description,
            turn=turn,
            impact=impact,
        )
        logger.info("记录 NPC 关键事件: npc=%s, type=%s, impact=%d", npc_id, event_type, impact)

    # ---- 查询 ----

    def get_memory_manager(self) -> MemoryManager:
        """获取内部记忆管理器（外部可用来注入 Prompt 或持久化）。"""
        return self._memory

    def get_npc_memory_context(self, npc_id: str) -> str:
        """获取指定 NPC 的记忆上下文文本（用于调试）。"""
        memory = self._memory.get_npc_memory(npc_id)
        return memory.get_prompt_context() if memory else "（无记忆）"

    # ---- 辅助 ----

    @staticmethod
    def _extract_npc_response(result: dict[str, Any]) -> str:
        """从对话生成结果中提取 NPC 的回应文本。

        对话输出格式（归一化后）：narrative 字段含 NPC 台词。
        降级时 narrative 是兜底文案，也一并记录。
        """
        # 优先从 narrative_segments 中找 dialogue
        segments = result.get("narrative_segments", [])
        for seg in segments:
            if seg.get("type") == "dialogue" and seg.get("text"):
                return str(seg["text"])
        # 退化为 narrative 全文
        return str(result.get("narrative", ""))


if __name__ == "__main__":
    # 自测：用 FakeLLM 验证流程（不依赖真实 LLM）
    import sys
    from pathlib import Path

    AGENT_SRC = Path(__file__).resolve().parent
    sys.path.insert(0, str(AGENT_SRC))

    from ai_agent_framework.config.settings import LLMConfig
    from llm_adapter import NarrativeLLMAdapter

    print("=== NPCDialogueGenerator 自测（FakeLLM）===")
    config = LLMConfig(provider="fake", model="fake")
    adapter = NarrativeLLMAdapter(config)

    generator = NPCDialogueGenerator(adapter)

    # 注册 NPC
    master_card = {
        "id": "master",
        "name": "玄清真人",
        "personality": {
            "traits": ["严厉", "护短"],
            "values": ["门派荣誉"],
            "dislikes": ["浮夸"],
            "speaking_style": "言简意赅",
        },
        "current_affinity": 5,
    }
    scene = {"id": "trial_grounds", "name": "试炼场", "description": "测灵石所在"}
    generator.register_npc("master", master_card, scene)

    # 对话（FakeLLM 会降级，但流程能跑通）
    print("\n--- 第 1 轮对话 ---")
    r1 = generator.talk("master", "拜见师父", turn=1)
    print(f"  degraded={r1.get('degraded')}, narrative={r1.get('narrative', '')[:50]}")

    print("\n--- 第 2 轮对话 ---")
    r2 = generator.talk("master", "请教修炼之法", turn=2)
    print(f"  degraded={r2.get('degraded')}, narrative={r2.get('narrative', '')[:50]}")

    # 查看记忆
    print("\n--- master 的记忆上下文 ---")
    print(generator.get_npc_memory_context("master"))

    # 记录关键事件
    print("\n--- 记录关键事件 ---")
    generator.record_event("master", "helped", "玩家帮玄清真人解围", turn=3, impact=10)
    print(generator.get_npc_memory_context("master"))

    print("\n=== 自测完成 ===")
