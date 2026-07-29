from pathlib import Path

import pytest

from app.engine import ConfigurationError, GameEngine, InvalidAction
from app.engine.models import SceneConfig
from app.engine.realm import RealmCalculator
from app.schemas.game_state import GameState


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


@pytest.mark.parametrize("sect", ["xuanqing", "shenwu", "fulong", "hongchen"])
def test_formal_content_reaches_free_exploration(sect):
    from app.schemas.game_state import WorldState

    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(world=WorldState(flags={"game_start": True}))

    for _ in range(30):
        if state.current_scene_id == "free_exploration":
            break
        choices = engine.available_choices(state)
        assert choices
        preferred = f"choose_{sect}"
        choice = next((item for item in choices if item.id == preferred), choices[0])
        state = engine.process_action(state, "choice", choice.id).state

    assert state.current_scene_id == "free_exploration"
    assert state.world.flags[f"{sect}_disciple"] is True
    assert state.world.flags["induction_completed"] is True


def test_choice_narrative_context_uses_destination_scene():
    from app.schemas.game_state import WorldState

    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(world=WorldState(flags={"game_start": True}))

    result = engine.process_action(state, "choice", "proceed_to_awakening")

    assert result.state.current_scene_id == "00_awakening_selection:awakening_ceremony"
    assert result.event_context["scene"]["scene_id"] == result.state.current_scene_id
    assert result.event_context["previous_scene"]["scene_id"] == "start"
    assert "测灵石" in result.event_context["scene"]["description"]


@pytest.mark.parametrize("sect", ["xuanqing", "shenwu", "fulong", "hongchen"])
def test_sect_choice_is_exclusive_and_routes_to_matching_trial(sect):
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(current_scene_id="00_awakening_selection:sect_selection")
    state.world.flags.update(
        {f"sect_chosen_{name}": True for name in ("xuanqing", "shenwu", "fulong", "hongchen")}
    )

    journey = engine.process_action(state, "choice", f"choose_{sect}")
    assert journey.state.world.flags[f"sect_chosen_{sect}"] is True
    assert all(
        journey.state.world.flags[f"sect_chosen_{other}"] is (other == sect)
        for other in ("xuanqing", "shenwu", "fulong", "hongchen")
    )

    arrival = engine.process_action(journey.state, "choice", "arrive_at_gate")
    assert [choice.id for choice in arrival.available_choices] == [f"begin_{sect}_trial"]

    trial = engine.process_action(arrival.state, "choice", f"begin_{sect}_trial")
    assert trial.state.current_scene_id.startswith(f"01_{sect}_trial:")


def test_xuanqing_heart_trial_exposes_narrative_choices_before_result():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(current_scene_id="01_xuanqing_trial:heart_trial")

    choices = engine.available_choices(state)

    assert [choice.id for choice in choices] == [
        "touch_wandao_stele",
        "meditate_before_stele",
    ]
    assert all("领取弟子凭证" not in choice.text for choice in choices)

    result = engine.process_action(state, "choice", "meditate_before_stele")
    assert result.state.current_scene_id == "01_xuanqing_trial:result"
    assert result.state.world.flags["xuanqing_heart_trial_meditated"] is True
    assert result.available_choices[0].id == "accept_trial_result"


def test_asking_xuanqing_guide_does_not_start_written_trial():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(current_scene_id="01_xuanqing_trial:arriving")

    asked = engine.process_action(state, "choice", "ask_guide_about_trial")

    assert asked.scene_changed is False
    assert asked.state.current_scene_id == "01_xuanqing_trial:arriving"
    assert asked.state.world.flags["xuanqing_prepared_carefully"] is True
    assert [choice.id for choice in asked.available_choices] == [
        "proceed_after_trial_briefing",
        "observe_mountain_before_trial",
    ]

    proceeded = engine.process_action(
        asked.state, "choice", "proceed_after_trial_briefing"
    )
    assert proceeded.state.current_scene_id == "01_xuanqing_trial:written_trial"


@pytest.mark.parametrize(
    ("scene_id", "question_id", "flag", "continue_id"),
    [
        (
            "00_awakening_selection:root_result",
            "ask_about_result",
            "spirit_root_explained",
            "continue_after_root_explanation",
        ),
        (
            "01_fulong_trial:oath_trial",
            "ask_oath_duty",
            "fulong_oath_questioned",
            "swear_after_clarification",
        ),
        (
            "02_xuanqing_induction:academy_assignment",
            "ask_about_academies",
            "xuanqing_induction_inquisitive",
            "choose_academy_after_explanation",
        ),
        (
            "02_shenwu_induction:army_assignment",
            "ask_about_unit",
            "shenwu_induction_inquisitive",
            "report_after_unit_explanation",
        ),
        (
            "02_fulong_induction:status_assignment",
            "ask_about_palace_status",
            "fulong_induction_inquisitive",
            "settle_after_status_explanation",
        ),
        (
            "02_hongchen_induction:role_assignment",
            "ask_about_new_role",
            "hongchen_induction_inquisitive",
            "begin_role_after_explanation",
        ),
    ],
)
def test_inquiry_choices_wait_for_explicit_progression(
    scene_id, question_id, flag, continue_id
):
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(current_scene_id=scene_id)

    answered = engine.process_action(state, "choice", question_id)

    assert answered.scene_changed is False
    assert answered.state.current_scene_id == scene_id
    assert answered.state.world.flags[flag] is True
    choice_ids = [choice.id for choice in answered.available_choices]
    assert question_id not in choice_ids
    assert continue_id in choice_ids


def test_free_exploration_actions_apply_whitelisted_effects():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(current_scene_id="free_exploration")

    cultivated = engine.process_action(state, "free_input", "我在静室打坐修炼")
    assert cultivated.state.player.cultivation == 3
    assert cultivated.event_context["authoritative_state_changes"]

    moved = engine.process_action(cultivated.state, "free_input", "前往藏经阁")
    assert moved.state.world.current_location == "藏经阁/藏经楼"
