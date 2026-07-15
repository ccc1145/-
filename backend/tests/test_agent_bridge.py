from app.engine import GameEngine
from app.services.agent_bridge import AgentBridge


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
    assert narrative.narrative == "由 Agent 生成的叙事"
    assert engine_result.state.player.cultivation == 5


def test_agent_failure_uses_deterministic_fallback(game_state):
    engine_result = GameEngine.default().process_action(
        game_state, "choice", "enter_trial"
    )

    def failing_provider(_context):
        raise TimeoutError("LLM timeout")

    narrative = AgentBridge(failing_provider).generate(engine_result)
    assert narrative.degraded is True
    assert narrative.narrative == engine_result.fallback_narrative
    assert narrative.narrative_segments[0].text == narrative.narrative


def test_empty_agent_output_also_degrades(game_state):
    engine_result = GameEngine.default().process_action(
        game_state, "choice", "enter_trial"
    )
    narrative = AgentBridge(lambda _context: {"narrative": ""}).generate(engine_result)
    assert narrative.degraded is True
