import pytest

from app.schemas.game_state import GameState, NPCState, PlayerState


@pytest.fixture
def game_state() -> GameState:
    return GameState(
        session_id="test-session",
        player=PlayerState(name="周泠锋"),
        npcs={"master": NPCState(id="master", name="玄清真人")},
    )
