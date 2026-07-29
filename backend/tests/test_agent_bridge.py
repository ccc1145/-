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
