"""Prompt 构建器：用 Jinja2 渲染 .j2 模板，注入 GameState + 场景上下文。

策划书 5.1 节定义了四类模板：
- system_prompt.j2          全局设定（作者身份、世界观、核心规则）
- scene_narrative.j2        场景叙事（根据 GameState + 玩家操作生成叙事）
- npc_dialogue.j2           NPC 对话（Day 4）
- free_input_response.j2    自由输入回应（Day 8）

本文件 Day 1 只实现前两个模板的渲染，后续按计划补全。
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
