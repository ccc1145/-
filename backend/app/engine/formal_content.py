"""Adapt the authored content YAML files to the deterministic runtime model."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.engine.errors import ConfigurationError
from app.engine.models import EventConfig, SceneConfig


SECTS = ("xuanqing", "shenwu", "fulong", "hongchen")


def _scene_id(event_id: str, local_id: str) -> str:
    if event_id == "00_awakening_selection" and local_id == "world_intro":
        return "start"
    return f"{event_id}:{local_id}"


def _normalise_effect(effect: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(effect)
    if result.get("type") == "set_flag":
        result.setdefault("value", True)
    return result


def _reward_effects(reward: dict[str, Any] | None) -> list[dict[str, Any]]:
    reward = reward or {}
    effects: list[dict[str, Any]] = []
    cultivation = int(reward.get("cultivation_gain", 0) or 0)
    if cultivation:
        effects.append(
            {
                "type": "modify_attribute",
                "target": "player.cultivation",
                "operation": "add",
                "value": cultivation,
            }
        )
    for item in reward.get("add_items", []):
        if item.get("item_id") == "low_grade_spirit_stone":
            effects.append(
                {
                    "type": "modify_attribute",
                    "target": "player.spirit_stones",
                    "operation": "add",
                    "value": int(item.get("quantity", 0)),
                }
            )
    for flag in reward.get("set_flags", []):
        effects.append({"type": "set_flag", "flag": flag, "value": True})
    return effects


def _load_major_events(content_dir: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in sorted((content_dir / "events" / "major").glob("*.yaml")):
        try:
            event = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"无法加载正式事件 {path.name}: {exc}") from exc
        if not isinstance(event, dict) or not isinstance(event.get("scenes"), dict):
            raise ConfigurationError(f"正式事件结构无效: {path.name}")
        events.append(event)
    if not events:
        raise ConfigurationError("content/events/major 中没有正式事件")
    return events


def load_formal_content(
    content_dir: str | Path,
) -> tuple[dict[str, SceneConfig], dict[str, str]]:
    """Load all authored major events and connect their stage boundaries.

    Authored trial and induction scenes intentionally leave choices to the Agent.
    Until structured intent adjudication is available, the runtime exposes one
    explicit stage-progression choice so every authored scene is playable.
    """

    root = Path(content_dir)
    events = _load_major_events(root)
    by_id = {event["event_id"]: event for event in events}
    scenes: dict[str, SceneConfig] = {}
    scene_events: dict[str, str] = {}

    for event in events:
        event_id = event["event_id"]
        local_scenes = event["scenes"]
        local_ids = list(local_scenes)

        for index, (local_id, source_scene) in enumerate(local_scenes.items()):
            raw = deepcopy(source_scene)
            runtime_id = _scene_id(event_id, local_id)
            raw["scene_id"] = runtime_id

            choices: list[dict[str, Any]] = []
            for choice in raw.get("choices", []) or []:
                adapted = deepcopy(choice)
                next_scene = adapted.get("next_scene")
                if next_scene:
                    adapted["next_scene"] = _scene_id(event_id, next_scene)
                adapted["effects"] = [
                    _normalise_effect(effect)
                    for effect in adapted.get("effects", []) or []
                ]
                if adapted.get("id", "").startswith("choose_"):
                    selected_sect = adapted["id"].removeprefix("choose_")
                    adapted["effects"] = [
                        {
                            "type": "set_flag",
                            "flag": f"sect_chosen_{sect}",
                            "value": sect == selected_sect,
                        }
                        for sect in SECTS
                    ]
                choices.append(adapted)

            # The authored Xuanqing heart trial is Agent-driven and therefore
            # has no YAML choices. Expose its two narrative decisions as real
            # engine choices so the UI cannot jump straight to the result.
            if not choices and event_id == "01_xuanqing_trial" and local_id == "heart_trial":
                next_scene = _scene_id(event_id, "result")
                choices.extend(
                    [
                        {
                            "id": "touch_wandao_stele",
                            "text": "直接触碰碑文，静观心镜显化",
                            "next_scene": next_scene,
                            "effects": [
                                {
                                    "type": "set_flag",
                                    "flag": "xuanqing_heart_trial_direct",
                                    "value": True,
                                }
                            ],
                        },
                        {
                            "id": "meditate_before_stele",
                            "text": "先盘膝打坐，感受此地灵力流动",
                            "next_scene": next_scene,
                            "effects": [
                                {
                                    "type": "set_flag",
                                    "flag": "xuanqing_heart_trial_meditated",
                                    "value": True,
                                }
                            ],
                        },
                    ]
                )

            if not choices and index < len(local_ids) - 1:
                next_local = local_ids[index + 1]
                choices.append(
                    {
                        "id": f"continue_to_{next_local}",
                        "text": "继续下一阶段",
                        "next_scene": _scene_id(event_id, next_local),
                    }
                )

            if not choices and event_id == "00_awakening_selection":
                opening_rewards = _reward_effects(event.get("reward"))
                for sect in SECTS:
                    trial_id = f"01_{sect}_trial"
                    trial = by_id[trial_id]
                    first_scene = next(iter(trial["scenes"]))
                    choices.append(
                        {
                            "id": f"begin_{sect}_trial",
                            "text": "持宗门凭证，参加入门试炼",
                            "condition": {
                                "type": "flag",
                                "flag": f"sect_chosen_{sect}",
                                "equals": True,
                            },
                            "effects": opening_rewards,
                            "next_scene": _scene_id(trial_id, first_scene),
                        }
                    )

            if not choices and event_id.startswith("01_"):
                sect = event_id.removeprefix("01_").removesuffix("_trial")
                induction_id = f"02_{sect}_induction"
                induction = by_id[induction_id]
                first_scene = next(iter(induction["scenes"]))
                choices.append(
                    {
                        "id": "accept_trial_result",
                        "text": "领取弟子凭证，正式入宗",
                        "effects": _reward_effects(event.get("reward")),
                        "next_scene": _scene_id(induction_id, first_scene),
                    }
                )

            if not choices and event_id.startswith("02_"):
                choices.append(
                    {
                        "id": "enter_free_exploration",
                        "text": "开始宗门生活",
                        "effects": _reward_effects(event.get("reward")),
                        "next_scene": "free_exploration",
                    }
                )

            raw["choices"] = choices
            try:
                scene = SceneConfig.model_validate(raw)
            except Exception as exc:
                raise ConfigurationError(
                    f"正式事件场景无法适配: {event_id}/{local_id}: {exc}"
                ) from exc
            if runtime_id in scenes:
                raise ConfigurationError(f"正式事件场景 ID 重复: {runtime_id}")
            scenes[runtime_id] = scene
            scene_events[runtime_id] = event_id

    exploration = SceneConfig(
        scene_id="free_exploration",
        name="宗门自由探索",
        description="入门试炼已经结束。你可以在宗门中修炼、交谈、探索或承接任务。",
        mood="自由、日常、充满可能",
        free_input_enabled=True,
        choices=[],
        agent_guidance={
            "setting_details": ["根据玩家所选宗门呈现对应地点、门规与日常生活。"],
            "sensory_details": ["结合当前地点与时辰描写宗门环境。"],
            "npc_behavior_hints": ["NPC 必须遵循角色卡，不得知晓其知识范围外的信息。"],
        },
    )
    scenes[exploration.scene_id] = exploration
    scene_events[exploration.scene_id] = "free_exploration"

    # Validate the connected runtime graph with the existing engine contract.
    EventConfig(event_id="formal_content", name="正式内容", scenes=scenes)
    return scenes, scene_events
