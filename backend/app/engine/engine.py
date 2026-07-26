"""Deterministic action orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.engine.conditions import ConditionEvaluator
from app.engine.content import builtin_content, load_event_directory
from app.engine.formal_content import load_formal_content
from app.engine.effects import EffectApplier
from app.engine.errors import ConfigurationError, InvalidAction
from app.engine.models import ChoiceConfig, EffectConfig, EngineResult, SceneConfig
from app.engine.realm import RealmCalculator
from app.schemas.game_state import Choice, GameState


class GameEngine:
    def __init__(
        self, scenes: dict[str, SceneConfig], scene_events: dict[str, str] | None = None
    ) -> None:
        if "start" not in scenes:
            raise ConfigurationError("内容必须包含 start 场景")
        self._scenes = scenes
        self._scene_events = scene_events or {}
        self._conditions = ConditionEvaluator()
        self._effects = EffectApplier()
        self._realms = RealmCalculator()
        self._validate_links()

    @classmethod
    def default(cls) -> "GameEngine":
        scenes, scene_events = builtin_content()
        return cls(scenes, scene_events)

    @classmethod
    def from_event_directory(cls, path: str | Path) -> "GameEngine":
        scenes, scene_events = load_event_directory(path)
        return cls(scenes, scene_events)

    @classmethod
    def from_formal_content(cls, path: str | Path) -> "GameEngine":
        scenes, scene_events = load_formal_content(path)
        return cls(scenes, scene_events)

    def _validate_links(self) -> None:
        for scene in self._scenes.values():
            choice_ids: set[str] = set()
            for choice in scene.choices:
                if choice.id in choice_ids:
                    raise ConfigurationError(
                        f"场景 {scene.scene_id} 包含重复选项: {choice.id}"
                    )
                choice_ids.add(choice.id)
                if choice.next_scene and choice.next_scene not in self._scenes:
                    raise ConfigurationError(
                        f"选项 {choice.id} 指向不存在场景: {choice.next_scene}"
                    )

    def _scene(self, scene_id: str) -> SceneConfig:
        try:
            return self._scenes[scene_id]
        except KeyError as exc:
            raise InvalidAction(f"当前场景不存在: {scene_id}") from exc

    def available_choices(self, state: GameState) -> list[Choice]:
        scene = self._scene(state.current_scene_id)
        return [
            Choice(id=choice.id, text=choice.text)
            for choice in scene.choices
            if self._conditions.evaluate(choice.condition, state)
        ]

    def scene(self, scene_id: str) -> SceneConfig:
        """Expose validated scene metadata to the API and narrative bridge."""
        return self._scene(scene_id)

    def process_action(
        self, state: GameState, action_type: str, payload: str
    ) -> EngineResult:
        """Process one action without mutating the caller's GameState."""

        if action_type not in {"choice", "free_input"}:
            raise InvalidAction(f"不支持的动作类型: {action_type}")
        if not isinstance(payload, str) or not payload.strip():
            raise InvalidAction("动作内容不能为空")

        working_state = state.model_copy(deep=True)
        previous_scene = working_state.current_scene_id
        working_state.turn_count += 1

        if action_type == "free_input":
            scene = self._scene(previous_scene)
            if not scene.free_input_enabled:
                raise InvalidAction("当前场景不允许自由输入")
            changes = self._apply_free_input_effects(working_state, payload.strip())
            return EngineResult(
                state=working_state,
                event_context={
                    "request_type": "free_input_response",
                    "event_id": self._scene_events.get(previous_scene),
                    "scene": scene.model_dump(),
                    "player_input": payload.strip(),
                    "authoritative_state_changes": changes,
                },
                available_choices=self.available_choices(working_state),
                scene_changed=False,
                game_over=scene.game_over,
                free_input_enabled=scene.free_input_enabled,
                fallback_narrative=f"你说出“{payload.strip()}”，四周暂时没有明显变化。",
            )

        scene = self._scene(previous_scene)
        choice = self._find_choice(scene, payload, working_state)
        changes = [
            self._effects.apply(working_state, effect) for effect in choice.effects
        ]
        self._realms.update(working_state)
        if choice.next_scene:
            working_state.current_scene_id = choice.next_scene
        next_scene = self._scene(working_state.current_scene_id)

        return EngineResult(
            state=working_state,
            event_context=self._event_context(
                previous_scene=scene,
                current_scene=next_scene,
                choice=choice,
                changes=changes,
                payload=payload,
            ),
            available_choices=self.available_choices(working_state),
            scene_changed=previous_scene != working_state.current_scene_id,
            game_over=next_scene.game_over,
            free_input_enabled=next_scene.free_input_enabled,
            fallback_narrative=choice.fallback_narrative,
        )

    def _apply_free_input_effects(
        self, state: GameState, text: str
    ) -> list[dict[str, Any]]:
        """Apply a small, auditable whitelist of free-action effects."""
        changes: list[dict[str, Any]] = []

        for npc_id, npc in state.npcs.items():
            if npc.name not in text and npc_id not in text:
                continue
            hostile = any(word in text for word in ("挑衅", "辱骂", "威胁", "攻击", "嘲讽"))
            friendly = any(word in text for word in ("行礼", "道谢", "请教", "交谈", "问候", "送礼"))
            if hostile or friendly:
                changes.append(
                    self._effects.apply(
                        state,
                        EffectConfig(
                            type="modify_npc_affinity",
                            target=npc_id,
                            value=-3 if hostile else 1,
                        ),
                    )
                )
            break

        if state.current_scene_id != "free_exploration":
            return changes

        if any(word in text for word in ("修炼", "打坐", "吐纳", "运功")):
            changes.append(
                self._effects.apply(
                    state,
                    EffectConfig(
                        type="modify_attribute",
                        target="player.cultivation",
                        value=3,
                    ),
                )
            )
        if any(word in text for word in ("休息", "睡觉", "疗伤")):
            for target, value in (
                ("player.hp", state.player.max_hp or 100),
                ("player.mp", state.player.max_mp or 50),
            ):
                changes.append(
                    self._effects.apply(
                        state,
                        EffectConfig(
                            type="modify_attribute",
                            target=target,
                            operation="set",
                            value=value,
                        ),
                    )
                )

        locations = {
            "大殿": "宗门大殿",
            "演武场": "演武场/修炼台",
            "修炼台": "演武场/修炼台",
            "静室": "静室",
            "后山": "后山/秘境入口",
            "藏经阁": "藏经阁/藏经楼",
            "藏经楼": "藏经阁/藏经楼",
        }
        if any(word in text for word in ("前往", "移动", "去", "走到")):
            for keyword, location in locations.items():
                if keyword in text:
                    before = state.world.current_location
                    state.world.current_location = location
                    changes.append(
                        {
                            "type": "move",
                            "target": "world.current_location",
                            "before": before,
                            "after": location,
                        }
                    )
                    break
        return changes

    def _find_choice(
        self, scene: SceneConfig, choice_id: str, state: GameState
    ) -> ChoiceConfig:
        for choice in scene.choices:
            if choice.id == choice_id and self._conditions.evaluate(
                choice.condition, state
            ):
                return choice
        raise InvalidAction(f"当前场景不可选择: {choice_id}")

    def _event_context(
        self,
        previous_scene: SceneConfig,
        current_scene: SceneConfig,
        choice: ChoiceConfig,
        changes: list[dict[str, Any]],
        payload: str,
    ) -> dict[str, Any]:
        return {
            "request_type": "scene_narrative",
            "event_id": self._scene_events.get(current_scene.scene_id),
            # Narrative and displayed choices must describe the same scene.
            "scene": current_scene.model_dump(),
            "previous_scene": previous_scene.model_dump(),
            "player_input": {"type": "choice", "id": payload, "text": choice.text},
            "authoritative_state_changes": changes,
            "next_scene_id": current_scene.scene_id,
            "agent_guidance": current_scene.agent_guidance,
        }
