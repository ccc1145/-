"""Agent 桥接服务：调用人员C 的 NarrativeController 生成叙事。"""
import os
import logging
from typing import Any

from narrative_controller import NarrativeController
from llm_adapter import NarrativeLLMAdapter
from memory import MemoryManager
from world_knowledge import get_all_world_knowledge, get_preset_narrative
from ai_agent_framework.config.settings import LLMConfig

logger = logging.getLogger(__name__)


class AgentBridge:
    def __init__(self):
        provider = os.getenv("LLM_PROVIDER", "deepseek")
        model = os.getenv("LLM_MODEL", "deepseek-chat")
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "")

        llm_config_kwargs = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        if base_url:
            llm_config_kwargs["base_url"] = base_url

        llm_config = LLMConfig(**llm_config_kwargs)
        self.llm_adapter = NarrativeLLMAdapter(llm_config)
        self.controller = NarrativeController(llm_adapter=self.llm_adapter)
        self.memory = MemoryManager()
    def generate(self, engine_result: Any, action_type: str, payload: str) -> dict:
        try:
            state = engine_result.state
            game_state_dict = state.dict()

            current_scene = {
                "id": state.current_scene_id,
                "description": state.world.current_location,
                "mood": "",
            }

            player_input = {
                "type": action_type,
                "value": payload,
            }

            event_context = getattr(engine_result, 'state_changes', {})

            memory_ctx = self.memory.get_prompt_context()

            npc_cards = {}
            for npc_id, npc_obj in state.npcs.items():
                npc_cards[npc_id] = {
                    "name": npc_obj.name,
                    "personality": {"traits": [], "speaking_style": ""},
                    "current_affinity": npc_obj.affinity,
                }


            result = self.controller.generate_scene_narrative(
                game_state=game_state_dict,
                current_scene=current_scene,
                player_input=player_input,
                event_context=event_context,
                memory=memory_ctx,
                npc_cards=npc_cards,
            )

            narrative_text = result.get("narrative", "")
            if not result.get("degraded"):
                self.memory.add_turn(
                    turn=state.turn_count,
                    player_input=payload,
                    narrative=narrative_text,
                )

            return {
                "narrative": narrative_text,
                "narrative_segments": result.get("narrative_segments", []),
                "thought": result.get("thought", ""),
                "degraded": result.get("degraded", False),
            }
        except Exception as e:
            logger.exception("Agent generation failed")
            scene_id = engine_result.state.current_scene_id
            fallback_text = get_preset_narrative(scene_id)
            return {
                "narrative": fallback_text,
                "narrative_segments": [{"type": "narration", "text": fallback_text}],
                "thought": f"DEGRADED: {e}",
                "degraded": True,
            }

    def reset_memory(self):
        self.memory.clear()