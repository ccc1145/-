"""YAML content loading plus a temporary built-in entrance trial."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.engine.errors import ConfigurationError
from app.engine.models import EventConfig, SceneConfig


def load_event_directory(
    path: str | Path,
) -> tuple[dict[str, SceneConfig], dict[str, str]]:
    directory = Path(path)
    if not directory.exists():
        raise ConfigurationError(f"内容目录不存在: {directory}")

    scenes: dict[str, SceneConfig] = {}
    scene_events: dict[str, str] = {}
    for file_path in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))):
        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
            event = EventConfig.model_validate(raw)
        except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
            raise ConfigurationError(
                f"无法加载事件配置 {file_path.name}: {exc}"
            ) from exc
        for key, scene in event.scenes.items():
            if key != scene.scene_id:
                raise ConfigurationError(
                    f"场景键与 scene_id 不一致: {key}/{scene.scene_id}"
                )
            if key in scenes:
                raise ConfigurationError(f"重复场景 ID: {key}")
            scenes[key] = scene
            scene_events[key] = event.event_id
    if not scenes:
        raise ConfigurationError(f"内容目录中没有事件 YAML: {directory}")
    return scenes, scene_events


def builtin_content() -> tuple[dict[str, SceneConfig], dict[str, str]]:
    """Return deterministic fixtures until the content branch is published."""

    event_data: dict[str, Any] = {
        "event_id": "entrance_trial",
        "name": "入门试炼",
        "scenes": {
            "start": {
                "scene_id": "start",
                "name": "青云山门",
                "choices": [
                    {
                        "id": "enter_trial",
                        "text": "踏入试炼场",
                        "effects": [
                            {
                                "type": "modify_attribute",
                                "target": "player.cultivation",
                                "operation": "add",
                                "value": 5,
                            },
                            {
                                "type": "set_flag",
                                "flag": "entered_trial",
                                "value": True,
                            },
                        ],
                        "next_scene": "trial_grounds",
                        "fallback_narrative": "你深吸一口气，踏入试炼场。中央立着一块三尺高的测灵石，散发着淡淡青光。",
                    },
                    {
                        "id": "look_around",
                        "text": "环顾四周，观察环境",
                        "next_scene": "start_observation",
                        "fallback_narrative": "你环顾四周，发现路边有一株奇异的灵芝，远处几名新弟子正在低声交谈。",
                    },
                ],
            },
            "start_observation": {
                "scene_id": "start_observation",
                "name": "山门外",
                "choices": [
                    {
                        "id": "enter_trial",
                        "text": "前往试炼场",
                        "next_scene": "trial_grounds",
                        "fallback_narrative": "你收回目光，沿石阶走入试炼场。",
                    },
                    {
                        "id": "talk_to_others",
                        "text": "与新弟子攀谈",
                        "effects": [
                            {
                                "type": "set_flag",
                                "flag": "met_fellow_disciples",
                                "value": True,
                            }
                        ],
                        "next_scene": "start_observation",
                        "fallback_narrative": "你与几名新弟子互通姓名，对试炼多了几分了解。",
                    },
                ],
            },
            "trial_grounds": {
                "scene_id": "trial_grounds",
                "name": "试炼场",
                "description": "试炼场中央立着一块测灵石",
                "agent_guidance": {
                    "sensory_details": ["测灵石触感冰凉", "注入灵气后会发热"]
                },
                "choices": [
                    {
                        "id": "touch_stone",
                        "text": "将手放在测灵石上",
                        "effects": [
                            {
                                "type": "modify_attribute",
                                "target": "player.cultivation",
                                "operation": "add",
                                "value": 10,
                            },
                            {
                                "type": "set_flag",
                                "flag": "trial_completed",
                                "value": True,
                            },
                        ],
                        "next_scene": "trial_result",
                        "fallback_narrative": "你将手放在测灵石上，灵光沿着石面纹路逐次亮起。玄清真人微微颔首。",
                    },
                    {
                        "id": "hesitate",
                        "text": "犹豫不决，暗自观察其他弟子",
                        "effects": [
                            {
                                "type": "modify_npc_affinity",
                                "target": "master",
                                "value": -5,
                            }
                        ],
                        "next_scene": "trial_hesitate",
                        "fallback_narrative": "你迟迟没有上前，玄清真人的目光中多了一分不悦。",
                    },
                ],
            },
            "trial_hesitate": {
                "scene_id": "trial_hesitate",
                "name": "试炼场",
                "choices": [
                    {
                        "id": "touch_stone",
                        "text": "定下心神，触碰测灵石",
                        "next_scene": "trial_grounds",
                        "fallback_narrative": "你定下心神，重新走到测灵石前。",
                    }
                ],
            },
            "trial_result": {
                "scene_id": "trial_result",
                "name": "试炼结果",
                "choices": [
                    {
                        "id": "express_gratitude",
                        "text": "弟子拜谢长老",
                        "effects": [
                            {
                                "type": "modify_npc_affinity",
                                "target": "master",
                                "value": 3,
                            }
                        ],
                        "next_scene": "master_selection",
                        "fallback_narrative": "你恭敬行礼，玄清真人眼中的神色缓和了几分。",
                    },
                    {
                        "id": "stay_silent",
                        "text": "默默退到一旁",
                        "next_scene": "master_selection",
                        "fallback_narrative": "你默默退到一旁，等待长老宣布结果。",
                    },
                    {
                        "id": "ask_question",
                        "text": "询问修炼之法",
                        "effects": [
                            {
                                "type": "modify_npc_affinity",
                                "target": "master",
                                "value": 2,
                            }
                        ],
                        "next_scene": "master_qa",
                        "fallback_narrative": "你拱手请教修炼之法，玄清真人略作思索后开口指点。",
                    },
                ],
            },
            "master_selection": {
                "scene_id": "master_selection",
                "name": "拜师",
                "game_over": True,
            },
            "master_qa": {
                "scene_id": "master_qa",
                "name": "长老答疑",
                "game_over": True,
            },
        },
    }
    event = EventConfig.model_validate(event_data)
    return event.scenes, {scene_id: event.event_id for scene_id in event.scenes}
