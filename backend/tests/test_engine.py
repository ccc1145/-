from pathlib import Path

import pytest

from app.engine import ConfigurationError, GameEngine, InvalidAction
from app.engine.models import SceneConfig
from app.engine.realm import RealmCalculator


def test_fixed_entrance_trial_flow_is_deterministic(game_state):
    engine = GameEngine.default()

    entered = engine.process_action(game_state, "choice", "enter_trial")
    assert entered.state.current_scene_id == "trial_grounds"
    assert entered.state.player.cultivation == 5
    assert entered.state.world.flags["entered_trial"] is True
    assert entered.scene_changed is True
    assert [choice.id for choice in entered.available_choices] == [
        "touch_stone",
        "hesitate",
    ]

    completed = engine.process_action(entered.state, "choice", "touch_stone")
    assert completed.state.current_scene_id == "trial_result"
    assert completed.state.player.cultivation == 15
    assert completed.state.player.realm.minor == 2
    assert completed.state.world.flags["trial_completed"] is True
    assert completed.state.npcs["master"].affinity == 0

    thanked = engine.process_action(completed.state, "choice", "express_gratitude")
    assert thanked.state.npcs["master"].affinity == 3
    assert thanked.game_over is True
    assert (
        thanked.event_context["authoritative_state_changes"][0]["target"]
        == "npcs.master.affinity"
    )


def test_invalid_choice_does_not_mutate_original_state(game_state):
    engine = GameEngine.default()
    snapshot = game_state.model_dump()

    with pytest.raises(InvalidAction):
        engine.process_action(game_state, "choice", "touch_stone")

    assert game_state.model_dump() == snapshot


def test_free_input_only_advances_turn(game_state):
    engine = GameEngine.default()
    result = engine.process_action(game_state, "free_input", "我要直接成为金丹修士")

    assert result.state.turn_count == 1
    assert result.state.player.cultivation == 0
    assert result.state.current_scene_id == "start"
    assert result.event_context["authoritative_state_changes"] == []


@pytest.mark.parametrize(
    "cultivation,minor", [(0, 1), (9, 1), (10, 2), (29, 2), (30, 3), (10000, 3)]
)
def test_realm_thresholds(game_state, cultivation, minor):
    game_state.player.cultivation = cultivation
    RealmCalculator().update(game_state)
    assert game_state.player.realm.major == "练气"
    assert game_state.player.realm.minor == minor


@pytest.mark.parametrize(
    "action_type,payload", [("spell", "x"), ("choice", ""), ("choice", "   ")]
)
def test_invalid_action_shape(game_state, action_type, payload):
    with pytest.raises(InvalidAction):
        GameEngine.default().process_action(game_state, action_type, payload)


def test_choice_condition_filters_unavailable_actions(game_state):
    scenes = {
        "start": SceneConfig.model_validate(
            {
                "scene_id": "start",
                "choices": [
                    {
                        "id": "secret",
                        "text": "隐藏选项",
                        "condition": {"type": "flag", "flag": "unlocked"},
                    }
                ],
            }
        )
    }
    engine = GameEngine(scenes)
    assert engine.available_choices(game_state) == []
    with pytest.raises(InvalidAction):
        engine.process_action(game_state, "choice", "secret")


def test_yaml_content_loader(tmp_path: Path, game_state):
    (tmp_path / "event.yaml").write_text(
        """
event_id: test
name: 测试事件
scenes:
  start:
    scene_id: start
    choices:
      - id: proceed
        text: 前进
        effects:
          - type: set_flag
            flag: proceeded
            value: true
        next_scene: end
  end:
    scene_id: end
    game_over: true
""".strip(),
        encoding="utf-8",
    )
    result = GameEngine.from_event_directory(tmp_path).process_action(
        game_state, "choice", "proceed"
    )
    assert result.state.world.flags["proceeded"] is True
    assert result.game_over is True


def test_invalid_content_is_rejected(tmp_path: Path):
    with pytest.raises(ConfigurationError, match="没有事件 YAML"):
        GameEngine.from_event_directory(tmp_path)

    bad = tmp_path / "bad.yaml"
    bad.write_text("event_id: broken", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="无法加载事件配置"):
        GameEngine.from_event_directory(tmp_path)


def test_invalid_scene_graph_is_rejected():
    with pytest.raises(ConfigurationError, match="start"):
        GameEngine({"other": SceneConfig(scene_id="other")})
    with pytest.raises(ConfigurationError, match="不存在场景"):
        GameEngine(
            {
                "start": SceneConfig.model_validate(
                    {
                        "scene_id": "start",
                        "choices": [{"id": "x", "text": "x", "next_scene": "missing"}],
                    }
                )
            }
        )
