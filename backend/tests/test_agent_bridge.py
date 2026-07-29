from app.engine import GameEngine
from app.services.agent_bridge import AgentBridge
from pathlib import Path

from app.schemas.game_state import GameState, WorldState


def test_agent_can_only_supply_narrative(game_state):
    engine_result = GameEngine.default().process_action(
        game_state, "choice", "enter_trial"
    )

    def malicious_provider(_context):
        return {
            "narrative": "由 Agent 生成的叙事",
            "narrative_segments": [
                {"type": "narration", "text": "由 Agent 生成的叙事"}
            ],
            "state_changes": {"player.cultivation": 9999},
        }

    narrative = AgentBridge(malicious_provider).generate(engine_result)
    assert narrative["narrative"] == "由 Agent 生成的叙事"
    assert engine_result.state.player.cultivation == 5


def test_agent_failure_uses_deterministic_fallback(game_state):
    engine_result = GameEngine.default().process_action(
        game_state, "choice", "enter_trial"
    )

    def failing_provider(_context):
        raise TimeoutError("LLM timeout")

    narrative = AgentBridge(failing_provider).generate(engine_result)
    assert narrative["degraded"] is True
    assert narrative["narrative"] == engine_result.fallback_narrative
    assert narrative["narrative_segments"][0]["text"] == narrative["narrative"]


def test_empty_agent_output_also_degrades(game_state):
    engine_result = GameEngine.default().process_action(
        game_state, "choice", "enter_trial"
    )
    narrative = AgentBridge(lambda _context: {"narrative": ""}).generate(engine_result)
    assert narrative["degraded"] is True


def test_choice_prompt_receives_selected_text_and_full_event_context():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(
        session_id="prompt-order-test",
        world=WorldState(flags={"game_start": True}),
    )
    engine_result = engine.process_action(state, "choice", "proceed_to_awakening")
    captured = {}

    class CapturingController:
        def generate_scene_narrative(self, **kwargs):
            captured.update(kwargs)
            return {
                "narrative": "场景已衔接",
                "narrative_segments": [{"type": "narration", "text": "场景已衔接"}],
                "degraded": False,
            }

    bridge = AgentBridge()
    bridge.controller = CapturingController()
    bridge.generate(engine_result, "choice", "proceed_to_awakening")

    assert captured["player_input"]["choice_text"] == "踏入中洲，参加启灵仪式"
    assert captured["event_context"]["previous_scene"]["scene_id"] == "start"
    assert (
        captured["event_context"]["scene"]["scene_id"]
        == "00_awakening_selection:awakening_ceremony"
    )
    assert "triggered_effects" in captured["event_context"]
    assert "尚未执行" in captured["current_scene"]["description"]
    assert "将手放在测灵石上" in captured["current_scene"]["description"]
    assert "前端只会显示以下系统选项" in captured["current_scene"]["description"]
    assert "不得提出上述列表之外" in captured["current_scene"]["description"]


def test_selected_sect_is_locked_in_agent_prompt():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(
        session_id="fulong-prompt-test",
        current_scene_id="00_awakening_selection:sect_selection",
    )
    engine_result = engine.process_action(state, "choice", "choose_fulong")
    captured = {}

    class CapturingController:
        def generate_scene_narrative(self, **kwargs):
            captured.update(kwargs)
            return {
                "narrative": "前往扶龙宫",
                "narrative_segments": [{"type": "narration", "text": "前往扶龙宫"}],
                "degraded": False,
            }

    bridge = AgentBridge()
    bridge.controller = CapturingController()
    bridge.generate(engine_result, "choice", "choose_fulong")

    description = captured["current_scene"]["description"]
    assert "宗门锁定：玩家已选择扶龙宫" in description
    assert "不得把地点、人物、称谓或试炼写成玄清宗" in description


def test_ninth_grade_spirit_root_is_described_as_supreme_not_inferior():
    engine = GameEngine.from_formal_content(Path(__file__).parents[2] / "content")
    state = GameState(
        session_id="supreme-root-prompt-test",
        current_scene_id="00_awakening_selection:awakening_ceremony",
    )
    state.player.spirit_root.type = "木"
    state.player.spirit_root.quality = 9
    engine_result = engine.process_action(state, "choice", "touch_the_stone")
    captured = {}

    class CapturingController:
        def generate_scene_narrative(self, **kwargs):
            captured.update(kwargs)
            return {
                "narrative": "木灵根九等",
                "narrative_segments": [{"type": "narration", "text": "木灵根九等"}],
                "degraded": False,
            }

    bridge = AgentBridge()
    bridge.controller = CapturingController()
    bridge.generate(engine_result, "choice", "touch_the_stone")

    description = captured["current_scene"]["description"]
    assert "木灵根，品质9等" in description
    assert "九等为极品" in description
    assert "严禁描写为驳杂、普通、欠佳或令人惋惜" in description
