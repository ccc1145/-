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

SECT_CONTEXTS = {
    "sect_chosen_xuanqing": ("玄清宗", "清妙山、悬空仙岛、虹桥与紫竹清气"),
    "sect_chosen_shenwu": ("神武门", "龙陨山脉、玄黑石门、演武声与金铁煞气"),
    "sect_chosen_fulong": ("扶龙宫", "神都皇城、承运殿、宫苑礼制与王朝气运"),
    "sect_chosen_hongchen": ("红尘阁", "神都玉带河、百花舫、红尘灯火与隐秘情报网络"),
}


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
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "1024")),
            "request_timeout": float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        }
        if base_url:
            llm_config_kwargs["base_url"] = base_url

        llm_config = LLMConfig(**llm_config_kwargs)
        self.llm_adapter = NarrativeLLMAdapter(llm_config)
        self.controller = NarrativeController(
            llm_adapter=self.llm_adapter,
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            backoff_base=0.2,
        )
        # Narrative memory must be isolated per game session. A shared memory
        # causes the second request to inherit dialogue from another playthrough.
        self._memories: dict[str, MemoryManager] = {}
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
            session_id = getattr(state, "session_id", "default") or "default"
            memory = self._memories.setdefault(session_id, MemoryManager())
            game_state_dict = state.dict()

            scene_data = engine_result.event_context.get("scene", {})
            pending_choice_texts = [
                choice.text if hasattr(choice, "text") else str(choice.get("text", ""))
                for choice in engine_result.available_choices
            ]
            narrative_boundary = ""
            if pending_choice_texts:
                narrative_boundary = (
                    "\n叙事边界：前端只会显示以下系统选项："
                    + "；".join(pending_choice_texts)
                    + "。这些动作尚未执行，严禁提前描写其动作、结果或后果。"
                    "叙事若引导玩家进行下一步，只能逐字使用上述选项，"
                    "不得提出上述列表之外的二选一、多选或行动建议。"
                )
            sect_boundary = ""
            selected_sects = [
                details
                for flag, details in SECT_CONTEXTS.items()
                if state.world.flags.get(flag, False)
            ]
            if selected_sects:
                sect_name, sect_setting = selected_sects[-1]
                other_sects = "、".join(
                    name for name, _ in SECT_CONTEXTS.values() if name != sect_name
                )
                sect_boundary = (
                    f"\n宗门锁定：玩家已选择{sect_name}。当前及后续叙事必须使用"
                    f"{sect_name}设定（{sect_setting}），不得把地点、人物、称谓或试炼"
                    f"写成{other_sects}。"
                )
            current_scene = {
                "id": state.current_scene_id,
                "name": scene_data.get("name", state.world.current_location),
                "description": scene_data.get("description", state.world.current_location)
                + sect_boundary
                + narrative_boundary,
                "mood": scene_data.get("mood", ""),
            }

            event_context = dict(engine_result.event_context)
            authored_input = event_context.get("player_input", {})
            if action_type == "choice" and isinstance(authored_input, dict):
                player_input = {
                    "type": "choice",
                    "choice_id": authored_input.get("id", payload),
                    "choice_text": authored_input.get("text", payload),
                }
            else:
                player_input = {"type": action_type, "text": payload, "value": payload}

            # Prompt templates historically call this list triggered_effects.
            event_context.setdefault(
                "triggered_effects",
                event_context.get("authoritative_state_changes", []),
            )

            memory_ctx = memory.get_prompt_context()

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
                memory.add_turn(
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

    def reset_memory(self, session_id: str | None = None):
        if session_id is None:
            self._memories.clear()
        else:
            self._memories.pop(session_id, None)
