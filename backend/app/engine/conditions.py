"""Safe condition evaluation for event choices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from operator import eq, ge, gt, le, lt, ne
from typing import Any, Callable

from app.engine.errors import ConfigurationError
from app.schemas.game_state import GameState

_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "eq": eq,
    "ne": ne,
    "gt": gt,
    "gte": ge,
    "lt": lt,
    "lte": le,
}


def _read_path(state: GameState, path: str) -> Any:
    value: Any = state
    for part in path.split("."):
        if isinstance(value, Mapping):
            if part not in value:
                raise ConfigurationError(f"条件字段不存在: {path}")
            value = value[part]
        elif hasattr(value, part):
            value = getattr(value, part)
        else:
            raise ConfigurationError(f"条件字段不存在: {path}")
    return value


class ConditionEvaluator:
    """Evaluate leaf conditions and nested all/any/not combinations."""

    def evaluate(self, condition: Any, state: GameState) -> bool:
        if condition is None:
            return True
        if isinstance(condition, Sequence) and not isinstance(condition, (str, bytes)):
            return all(self.evaluate(item, state) for item in condition)
        if not isinstance(condition, Mapping):
            raise ConfigurationError("condition 必须是对象、列表或 null")

        if "all" in condition:
            return all(self.evaluate(item, state) for item in condition["all"])
        if "any" in condition:
            return any(self.evaluate(item, state) for item in condition["any"])
        if "not" in condition:
            return not self.evaluate(condition["not"], state)

        condition_type = condition.get("type")
        if condition_type == "flag":
            flag = condition.get("flag")
            if not isinstance(flag, str) or not flag:
                raise ConfigurationError("flag 条件缺少 flag")
            return state.world.flags.get(flag, False) == condition.get("equals", True)
        if condition_type == "scene":
            return state.current_scene_id == condition.get("scene_id")
        if condition_type == "attribute":
            target = condition.get("target")
            operator_name = condition.get("operator", "eq")
            if not isinstance(target, str) or operator_name not in _COMPARATORS:
                raise ConfigurationError("attribute 条件的 target/operator 无效")
            try:
                return _COMPARATORS[operator_name](
                    _read_path(state, target), condition.get("value")
                )
            except TypeError as exc:
                raise ConfigurationError(f"条件值不可比较: {target}") from exc
        raise ConfigurationError(f"不支持的条件类型: {condition_type}")
