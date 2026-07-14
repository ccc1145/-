from pydantic import BaseModel
from typing import Optional, Dict, List

class PlayerState(BaseModel):
    name: str = "无名修士"
    cultivation: int = 0
    hp: int = 100
    max_hp: int = 100

class WorldState(BaseModel):
    scene_id: str = "start"
    flags: Dict[str, bool] = {}

class GameState(BaseModel):
    player: PlayerState = PlayerState()
    world: WorldState = WorldState()
    turn: int = 0