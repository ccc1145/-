import pytest

from app.engine.conditions import ConditionEvaluator
from app.engine.errors import ConfigurationError


def test_nested_condition_combinations(game_state):
    game_state.player.cultivation = 15
    game_state.world.flags["entered_trial"] = True
    evaluator = ConditionEvaluator()

    condition = {
        "all": [
            {"type": "flag", "flag": "entered_trial"},
            {
                "any": [
                    {
                        "type": "attribute",
                        "target": "player.cultivation",
                        "operator": "gte",
                        "value": 10,
                    },
                    {"type": "scene", "scene_id": "impossible"},
                ]
            },
            {"not": {"type": "flag", "flag": "blocked"}},
        ]
    }

    assert evaluator.evaluate(condition, game_state) is True
    assert evaluator.evaluate([condition, None], game_state) is True


@pytest.mark.parametrize(
    "operator,expected",
    [
        ("eq", True),
        ("ne", False),
        ("gt", True),
        ("gte", True),
        ("lt", False),
        ("lte", False),
    ],
)
def test_attribute_operators(game_state, operator, expected):
    game_state.player.cultivation = 15
    condition = {
        "type": "attribute",
        "target": "player.cultivation",
        "operator": operator,
        "value": 10 if operator not in {"eq", "ne"} else 15,
    }
    assert ConditionEvaluator().evaluate(condition, game_state) is expected


@pytest.mark.parametrize(
    "condition",
    [
        "invalid",
        {"type": "unknown"},
        {"type": "flag"},
        {"type": "attribute", "target": "missing.field"},
        {
            "type": "attribute",
            "target": "player.cultivation",
            "operator": "contains",
            "value": 1,
        },
        {"type": "attribute", "target": "player.name", "operator": "gt", "value": 1},
    ],
)
def test_invalid_conditions_are_rejected(game_state, condition):
    with pytest.raises(ConfigurationError):
        ConditionEvaluator().evaluate(condition, game_state)
