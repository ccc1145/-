"""MVP cultivation-to-realm rules."""

from app.schemas.game_state import GameState


class RealmCalculator:
    """Keep the MVP in Qi Refining levels 1-3 with explicit thresholds."""

    LEVEL_THRESHOLDS = ((30, 3), (10, 2), (0, 1))

    def update(self, state: GameState) -> None:
        cultivation = max(0, state.player.cultivation)
        state.player.cultivation = cultivation
        state.player.realm.major = "练气"
        for threshold, level in self.LEVEL_THRESHOLDS:
            if cultivation >= threshold:
                state.player.realm.minor = level
                return
