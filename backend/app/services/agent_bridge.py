"""Agent 桥接服务：调用人员C 的 NarrativeController 生成叙事。"""
import os
import logging
import sys
from pathlib import Path
from collections.abc import Callable
from typing import Any

# 允许服务模块被测试或脚本直接导入，不依赖 app.main 预先修改 sys.path。
PROJECT_ROOT = Path(__file__).resolve().parents[3]
for source_dir in (PROJECT_ROOT / "agent" / "src", PROJECT_ROOT / "ai_agent_framework" / "src"):
    source_path = str(source_dir)
    if source_path not in sys.path:
        sys.path.insert(0, source_path)

from narrative_controller import NarrativeController
from llm_adapter import NarrativeLLMAdapter
from memory import MemoryManager
from world_knowledge import get_all_world_knowledge, get_preset_narrative
from world_book_loader import NPCCardLoader, WorldBookLoader
from ai_agent_framework.config.settings import LLMConfig

logger = logging.getLogger(__name__)


class AgentBridge:
    def __init__(self, provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        self._provider = provider
        # DeepSeek exposes an OpenAI-compatible API, so the framework uses its
        # OpenAI-compatible client while requests still go to DeepSeek.
        provider = os.getenv("LLM_PROVIDER", "openai")
        model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "")

        llm_config_kwargs = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "640")),
            "request_timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
        }
        if base_url:
            llm_config_kwargs["base_url"] = base_url

        llm_config = LLMConfig(**llm_config_kwargs)
        self.llm_adapter = NarrativeLLMAdapter(llm_config)
        self.controller = NarrativeController(
            llm_adapter=self.llm_adapter,
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "20")),
            backoff_base=0,
        )
        self.memory = MemoryManager()
        self.world_books = WorldBookLoader(PROJECT_ROOT / "content")
        self.npc_cards = NPCCardLoader(PROJECT_ROOT / "content")
        self.world_books.load_all()
        self.npc_cards.load_all()
    def generate(
        self, engine_result: Any, action_type: str = "choice", payload: str = ""
    ) -> dict:
        if self._provider is not None:
            try:
                supplied = self._provider(engine_result.event_context)
                narrative = supplied.get("narrative", "").strip()
                if narrative:
                    return {
                        "narrative": narrative,
                        "narrative_segments": supplied.get(
                            "narrative_segments",
                            [{"type": "narration", "text": narrative}],
                        ),
                        "thought": supplied.get("thought", ""),
                        "degraded": False,
                    }
            except Exception:
                pass
            fallback_text = engine_result.fallback_narrative or get_preset_narrative(
                engine_result.state.current_scene_id
            )
            return {
                "narrative": fallback_text,
                "narrative_segments": [{"type": "narration", "text": fallback_text}],
                "thought": "Injected narrative provider unavailable or invalid",
                "degraded": True,
            }
        try:
            state = engine_result.state
            game_state_dict = state.dict()

            scene_data = engine_result.event_context.get("scene", {})
            current_scene = {
                "id": state.current_scene_id,
                "name": scene_data.get("name", state.world.current_location),
                "description": scene_data.get("description", state.world.current_location),
                "mood": scene_data.get("mood", ""),
            }

            player_input = {
                "type": action_type,
                "value": payload,
            }

            event_context = getattr(engine_result, 'state_changes', {})

            memory_ctx = self.memory.get_prompt_context()

            npc_cards = {}
            for npc_id, npc_obj in state.npcs.items():
                card = self.npc_cards.to_prompt_card(npc_id, npc_obj.affinity)
                npc_cards[npc_id] = card or {
                    "name": npc_obj.name,
                    "personality": {"traits": [], "speaking_style": ""},
                    "current_affinity": npc_obj.affinity,
                }

            combined_context = " ".join(
                [payload, current_scene["name"], current_scene["description"]]
            )
            for npc_id, card in self.npc_cards.get_all_npcs().items():
                if len(npc_cards) >= 4:
                    break
                if card.get("name", "") in combined_context or npc_id in combined_context:
                    npc_cards[npc_id] = self.npc_cards.to_prompt_card(npc_id)

            matched_entries = self.world_books.match(combined_context, max_entries=8)
            world_book_context = self.world_books.format_entries_for_prompt(matched_entries)


            if action_type == "free_input":
                result = self.controller.generate_free_input_response(
                    player_input=payload,
                    game_state=game_state_dict,
                    current_scene=current_scene,
                    memory=memory_ctx,
                    npc_cards=npc_cards,
                    world_book_context=world_book_context,
                    # Local intent recognition avoids a second DeepSeek request.
                    use_llm_intent=False,
                )
            else:
                result = self.controller.generate_scene_narrative(
                    game_state=game_state_dict,
                    current_scene=current_scene,
                    player_input=player_input,
                    event_context=event_context,
                    memory=memory_ctx,
                    npc_cards=npc_cards,
                    world_book_context=world_book_context,
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
                "intent": result.get("intent"),
                "is_ooc": result.get("is_ooc", False),
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
