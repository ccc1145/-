"""Validated content models and the engine's internal result contract."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.game_state import Choice, GameState


class EffectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["modify_attribute", "set_flag", "modify_npc_affinity"]
    target: str | None = None
    operation: Literal["add", "subtract", "set"] = "add"
    value: int | bool
    flag: str | None = None


class ChoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    condition: dict[str, Any] | list[Any] | None = None
    effects: list[EffectConfig] = Field(default_factory=list)
    next_scene: str | None = None
    fallback_narrative: str = "你作出了选择，四周的气息随之发生了微妙的变化。"


class SceneConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_id: str
    name: str = ""
    description: str = ""
    mood: str = ""
    free_input_enabled: bool = True
    choices: list[ChoiceConfig] = Field(default_factory=list)
    agent_guidance: dict[str, Any] = Field(default_factory=dict)
    game_over: bool = False


class EventConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str
    name: str
    trigger_conditions: list[dict[str, Any]] = Field(default_factory=list)
    scenes: dict[str, SceneConfig]


class EngineResult(BaseModel):
    """The only internal interface used by FastAPI and the narrative layer."""

    state: GameState
    event_context: dict[str, Any] = Field(default_factory=dict)
    available_choices: list[Choice] = Field(default_factory=list)
    scene_changed: bool = False
    game_over: bool = False
    free_input_enabled: bool = True
    fallback_narrative: str = ""
