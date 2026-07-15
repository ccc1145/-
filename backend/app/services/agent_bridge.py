"""Narrative boundary that cannot mutate authoritative engine state."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.engine.models import EngineResult
from app.schemas.game_state import NarrativeSegment


class NarrativeResult(BaseModel):
    narrative: str
    narrative_segments: list[NarrativeSegment] = Field(default_factory=list)
    thought: str | None = None
    degraded: bool = False


class AgentBridge:
    """Call a narrative provider and ignore any attempted state mutations."""

    def __init__(
        self, provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    ) -> None:
        self._provider = provider

    def generate(self, result: EngineResult) -> NarrativeResult:
        if self._provider is not None:
            try:
                raw = self._provider(result.event_context)
                narrative = NarrativeResult.model_validate(raw)
                if narrative.narrative.strip():
                    return narrative
            except Exception:
                pass

        fallback = result.fallback_narrative or "灵气流转，故事仍在继续。"
        return NarrativeResult(
            narrative=fallback,
            narrative_segments=[NarrativeSegment(type="narration", text=fallback)],
            thought="Agent unavailable or invalid; deterministic fallback used",
            degraded=True,
        )
