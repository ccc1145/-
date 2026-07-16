import pytest

from app.engine.effects import EffectApplier
from app.engine.errors import InvalidEffect
from app.engine.models import EffectConfig


def test_attribute_flag_and_affinity_effects(game_state):
    applier = EffectApplier()
    cultivation_change = applier.apply(
        game_state,
        EffectConfig(
            type="modify_attribute",
            target="player.cultivation",
            operation="add",
            value=10,
        ),
    )
    applier.apply(
        game_state, EffectConfig(type="set_flag", flag="trial_completed", value=True)
    )
    affinity_change = applier.apply(
        game_state,
        EffectConfig(type="modify_npc_affinity", target="master", value=150),
    )

    assert cultivation_change["before"] == 0
    assert cultivation_change["after"] == 10
    assert game_state.world.flags["trial_completed"] is True
    assert affinity_change["after"] == 100


def test_numeric_effects_clamp_and_support_operations(game_state):
    applier = EffectApplier()
    game_state.player.cultivation = 5
    applier.apply(
        game_state,
        EffectConfig(
            type="modify_attribute",
            target="player.cultivation",
            operation="subtract",
            value=20,
        ),
    )
    assert game_state.player.cultivation == 0

    applier.apply(
        game_state,
        EffectConfig(
            type="modify_attribute", target="player.hp", operation="set", value=999
        ),
    )
    assert game_state.player.hp == game_state.player.max_hp

    applier.apply(
        game_state,
        EffectConfig(
            type="modify_npc_affinity", target="master", operation="set", value=-200
        ),
    )
    assert game_state.npcs["master"].affinity == -100


@pytest.mark.parametrize(
    "effect",
    [
        EffectConfig(type="modify_attribute", target="player.name", value=1),
        EffectConfig(type="modify_attribute", target=None, value=1),
        EffectConfig(type="set_flag", flag=None, value=True),
        EffectConfig(type="set_flag", flag="bad", value=1),
        EffectConfig(type="modify_npc_affinity", target="missing", value=1),
    ],
)
def test_invalid_or_unsafe_effects_are_rejected(game_state, effect):
    with pytest.raises(InvalidEffect):
        EffectApplier().apply(game_state, effect)
