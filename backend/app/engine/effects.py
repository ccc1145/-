"""Whitelisted state mutations used by configured event choices."""

from __future__ import annotations

from typing import Any

from app.engine.errors import InvalidEffect
from app.engine.models import EffectConfig
from app.schemas.game_state import GameState

_NUMERIC_TARGETS = {
    "player.cultivation",
    "player.attributes.strength",
    "player.attributes.agility",
    "player.attributes.intelligence",
    "player.attributes.perception",
    "player.hp",
    "player.mp",
    "player.spirit_stones",
}


def _numeric_value(state: GameState, target: str) -> tuple[Any, str, int]:
    if target not in _NUMERIC_TARGETS:
        raise InvalidEffect(f"不允许修改字段: {target}")
    parent: Any = state
    parts = target.split(".")
    for part in parts[:-1]:
        parent = getattr(parent, part)
    field = parts[-1]
    current = getattr(parent, field)
    if not isinstance(current, int):
        raise InvalidEffect(f"字段不是整数: {target}")
    return parent, field, current


class EffectApplier:
    """Apply only explicitly supported effects and return an audit record."""

    def apply(self, state: GameState, effect: EffectConfig) -> dict[str, Any]:
        if effect.type == "modify_attribute":
            return self._modify_attribute(state, effect)
        if effect.type == "set_flag":
            return self._set_flag(state, effect)
        if effect.type == "modify_npc_affinity":
            return self._modify_npc_affinity(state, effect)
        raise InvalidEffect(f"不支持的效果类型: {effect.type}")

    def _modify_attribute(
        self, state: GameState, effect: EffectConfig
    ) -> dict[str, Any]:
        if not effect.target or isinstance(effect.value, bool):
            raise InvalidEffect("modify_attribute 需要 target 和整数 value")
        parent, field, before = _numeric_value(state, effect.target)
        if effect.operation == "add":
            after = before + effect.value
        elif effect.operation == "subtract":
            after = before - effect.value
        else:
            after = effect.value

        after = max(0, after)
        if effect.target == "player.hp" and state.player.max_hp is not None:
            after = min(after, state.player.max_hp)
        if effect.target == "player.mp" and state.player.max_mp is not None:
            after = min(after, state.player.max_mp)
        setattr(parent, field, after)
        return {
            "type": effect.type,
            "target": effect.target,
            "before": before,
            "after": after,
        }

    @staticmethod
    def _set_flag(state: GameState, effect: EffectConfig) -> dict[str, Any]:
        if not effect.flag or not isinstance(effect.value, bool):
            raise InvalidEffect("set_flag 需要 flag 和布尔 value")
        before = state.world.flags.get(effect.flag)
        state.world.flags[effect.flag] = effect.value
        return {
            "type": effect.type,
            "target": f"world.flags.{effect.flag}",
            "before": before,
            "after": effect.value,
        }

    @staticmethod
    def _modify_npc_affinity(state: GameState, effect: EffectConfig) -> dict[str, Any]:
        if (
            not effect.target
            or effect.target not in state.npcs
            or isinstance(effect.value, bool)
        ):
            raise InvalidEffect(f"NPC 不存在或 value 无效: {effect.target}")
        npc = state.npcs[effect.target]
        before = npc.affinity
        if effect.operation == "set":
            after = effect.value
        elif effect.operation == "subtract":
            after = before - effect.value
        else:
            after = before + effect.value
        npc.affinity = max(-100, min(100, after))
        return {
            "type": effect.type,
            "target": f"npcs.{effect.target}.affinity",
            "before": before,
            "after": npc.affinity,
        }
