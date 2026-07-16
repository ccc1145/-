"""Prompt 构建器：用 Jinja2 渲染 .j2 模板，注入 GameState + 场景上下文 + NPC 信息。

策划书 5.1 节定义了四类模板：
- system_prompt.j2          全局设定（作者身份、世界观、核心规则）
- scene_narrative.j2        场景叙事（根据 GameState + 玩家操作生成叙事）
- npc_dialogue.j2           NPC 对话（Day 4）
- free_input_response.j2    自由输入回应（Day 8）

Day 4 升级：补全 npc_dialogue 渲染方法，完整支持 GameState + 角色卡动态注入。
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# 模板目录：agent/prompt_templates/
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "prompt_templates"


class PromptBuilder:
    """渲染 Prompt 模板。

    用法：
        builder = PromptBuilder()
        system_prompt = builder.build_system_prompt(world_knowledge=..., current_scene=..., npc_cards=...)
        user_prompt = builder.build_scene_narrative_prompt(game_state=..., player_input=..., ...)
        npc_prompt = builder.build_npc_dialogue_prompt(npc=..., player_input=..., current_scene=..., dialogue_history=...)
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir or TEMPLATE_DIR)),
            # .j2 模板不转义（我们要原样输出中文叙事），关闭自动转义
            autoescape=select_autoescape(disabled_extensions=("j2",), default=False),
            trim_blocks=True,   # 块标签后第一个换行自动去除，模板更干净
            lstrip_blocks=True,  # 块标签前空白自动去除
        )

    def build_system_prompt(self, *, world_knowledge, current_scene, npc_cards) -> str:
        """渲染系统提示：作者身份 + 世界观 + 当前场景 + NPC 信息。"""
        return self._env.get_template("system_prompt.j2").render(
            world_knowledge=world_knowledge,
            current_scene=current_scene,
            npc_cards=npc_cards,
        )

    def build_scene_narrative_prompt(
        self,
        *,
        game_state,
        player_input,
        event_context,
        memory,
    ) -> str:
        """渲染场景叙事提示：当前状态 + 玩家操作 + 状态变化 + 最近事件。"""
        return self._env.get_template("scene_narrative.j2").render(
            game_state=game_state,
            player_input=player_input,
            event_context=event_context,
            memory=memory,
        )

    def build_npc_dialogue_prompt(
        self,
        *,
        npc,
        player_input,
        current_scene,
        dialogue_history,
    ) -> str:
        """渲染 NPC 对话提示：角色卡 + 玩家输入 + 关系状态 + 对话历史。

        Args:
            npc: NPC 角色卡 dict，需含 name / personality / current_affinity
            player_input: 玩家输入 dict，需含 text
            current_scene: 当前场景 dict，需含 name
            dialogue_history: 该 NPC 的对话历史 list[str] 或 list[dict]
        """
        return self._env.get_template("npc_dialogue.j2").render(
            npc=npc,
            player_input=player_input,
            current_scene=current_scene,
            dialogue_history=dialogue_history,
        )

    def build_free_input_response_prompt(
        self,
        *,
        player_input: str,
        intent: dict,
        game_state: dict,
        current_scene: dict,
        npc_cards: dict,
        memory: dict,
        is_ooc: bool = False,
        ooc_reason: str = "",
    ) -> str:
        """渲染自由输入回应提示：玩家输入 + 意图分类 + OOC 检测 + 上下文。

        Args:
            player_input: 玩家自由输入的原始文本
            intent: 意图分类结果 dict，含 intent/target/topic/confidence/method
            game_state: GameState v1.0
            current_scene: 当前场景 dict
            npc_cards: 在场 NPC 角色卡 dict
            memory: 记忆上下文 dict
            is_ooc: 是否检测到 OOC
            ooc_reason: OOC 原因说明
        """
        return self._env.get_template("free_input_response.j2").render(
            player_input=player_input,
            intent=intent,
            game_state=game_state,
            current_scene=current_scene,
            npc_cards=npc_cards,
            memory=memory,
            is_ooc=is_ooc,
            ooc_reason=ooc_reason,
        )
