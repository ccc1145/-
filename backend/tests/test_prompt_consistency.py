import sys
from pathlib import Path


AGENT_SRC = Path(__file__).resolve().parents[2] / "agent" / "src"
sys.path.insert(0, str(AGENT_SRC))

from prompt_builder import PromptBuilder


def test_scene_prompt_uses_authoritative_spirit_root():
    prompt = PromptBuilder().build_scene_narrative_prompt(
        game_state={
            "player": {
                "name": "测试者",
                "cultivation": 0,
                "spirit_root": {"type": "火", "quality": 2},
                "hp": 100,
                "max_hp": 100,
                "mp": 50,
                "max_mp": 50,
                "spirit_stones": 0,
                "skills": [],
            },
            "world": {"current_location": "启灵台"},
            "npcs": {},
        },
        player_input={"type": "choice", "choice_text": "触摸测灵石"},
        event_context={"triggered_effects": []},
        memory={"recent_events": []},
    )

    assert "灵根类型：火" in prompt
    assert "灵根品级：2等" in prompt
    assert "七品" not in prompt


def test_system_prompt_has_no_hard_coded_spirit_root_grade():
    prompt = PromptBuilder().build_system_prompt(
        world_knowledge=[],
        current_scene={"name": "启灵台", "description": "测灵", "mood": "肃静"},
        npc_cards={},
    )

    assert "火灵根，七品" not in prompt
    assert "玄清真人" not in prompt
    assert "GameState.player.spirit_root.quality" in prompt
