"""Narrative Controller：Agent 层核心调度器。

策划书 Day 5 任务：实现输出重试机制（3 次失败后降级）。
Day 8 扩展为完整 controller：含 OOC 检测、自由输入路由。

职责：
1. 组装 system_prompt + user_prompt（委托 PromptBuilder）
2. 调用 LLM（委托 NarrativeLLMAdapter）
3. 解析输出（委托 AgentOutputParser）
4. 失败重试（最多 3 次，含超时控制 + 指数退避）
5. 全部失败时降级（返回预设文案，保证游戏可运行）
6. 自由输入处理（委托 FreeInputProcessor：意图分类 + OOC 检测 + 回应生成）

Day 6-7 Polish：加指数退避重试间隔，更细日志级别
Day 8：集成 FreeInputProcessor，新增 generate_free_input_response 方法

输出对齐 docs/agent-io-format.md v1.0。
"""
from __future__ import annotations

import logging
import time
from typing import Any

from free_input_processor import FreeInputProcessor
from llm_adapter import NarrativeLLMAdapter
from parser import AgentOutputParser
from prompt_builder import PromptBuilder
from world_knowledge import get_all_world_knowledge, get_preset_narrative

logger = logging.getLogger(__name__)


class NarrativeController:
    """Agent 叙事生成调度器。

    用法：
        controller = NarrativeController(llm_adapter, max_retries=3, timeout=30.0)
        result = controller.generate_scene_narrative(
            game_state=..., current_scene=..., player_input=...,
            event_context=..., memory=..., npc_cards=...,
        )
        # result 是符合 agent-io-format.md 的 dict
    """

    def __init__(
        self,
        llm_adapter: NarrativeLLMAdapter,
        max_retries: int = 3,
        timeout: float = 30.0,
        backoff_base: float = 0.5,
    ) -> None:
        """
        Args:
            llm_adapter: LLM 适配器
            max_retries: 最大重试次数
            timeout: 单次 LLM 调用慢调用阈值（仅警告，不硬中断）
            backoff_base: 指数退避基础秒数。重试间隔 = backoff_base * 2^(attempt-1)
                         如 base=0.5 → 0.5s, 1s, 2s
        """
        self._llm = llm_adapter
        self._parser = AgentOutputParser()
        self._prompt_builder = PromptBuilder()
        self._free_input_processor = FreeInputProcessor(
            llm_adapter=llm_adapter,
            prompt_builder=self._prompt_builder,
        )
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_base = backoff_base

    # ---- 场景叙事生成（核心入口）----

    def generate_scene_narrative(
        self,
        *,
        game_state: dict[str, Any],
        current_scene: dict[str, Any],
        player_input: dict[str, Any],
        event_context: dict[str, Any],
        memory: dict[str, Any],
        npc_cards: dict[str, Any],
    ) -> dict[str, Any]:
        """生成场景叙事。

        Returns:
            符合 docs/agent-io-format.md 的 dict。成功时无 degraded 标记，
            降级时带 degraded: True。
        """
        # 1. 构建 Prompt
        system_prompt = self._prompt_builder.build_system_prompt(
            world_knowledge=get_all_world_knowledge(),
            current_scene=current_scene,
            npc_cards=npc_cards,
        )
        user_prompt = self._prompt_builder.build_scene_narrative_prompt(
            game_state=game_state,
            player_input=player_input,
            event_context=event_context,
            memory=memory,
        )

        # 2. 带重试的 LLM 调用
        return self._invoke_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            scene_id=current_scene.get("id", "default"),
            fallback_context={
                "scene_id": current_scene.get("id", "default"),
                "player_name": game_state.get("player", {}).get("name", "道友"),
            },
        )

    # ---- NPC 对话生成 ----

    def generate_npc_dialogue(
        self,
        *,
        npc: dict[str, Any],
        player_input: dict[str, Any],
        current_scene: dict[str, Any],
        dialogue_history: list[str],
        npc_knowledge: list | None = None,
        dialogue_examples: list | None = None,
        world_book_context: str = "",
    ) -> dict[str, Any]:
        """生成 NPC 对话回应。

        Args:
            npc: NPC 角色卡 dict
            player_input: 玩家输入 dict，含 text
            current_scene: 当前场景 dict
            dialogue_history: 对话历史 list[str]
            npc_knowledge: Day 10 新增，NPC 掌握的知识列表（限制 NPC 只说自己知道的事）
            dialogue_examples: Day 10 新增，对话示例列表（Few-shot 注入）
            world_book_context: Day 10 新增，关键词触发的世界观知识文本

        Returns:
            含 response / emotion / internal_thought 的 dict，降级时带 degraded 标记。
        """
        user_prompt = self._prompt_builder.build_npc_dialogue_prompt(
            npc=npc,
            player_input=player_input,
            current_scene=current_scene,
            dialogue_history=dialogue_history,
            npc_knowledge=npc_knowledge,
            dialogue_examples=dialogue_examples,
            world_book_context=world_book_context,
        )
        # NPC 对话复用 system_prompt 的世界观设定，但当前场景和 NPC 信息已在 user_prompt 里
        system_prompt = self._prompt_builder.build_system_prompt(
            world_knowledge=get_all_world_knowledge(),
            current_scene=current_scene,
            npc_cards={npc.get("id", "npc"): npc} if npc else {},
            world_book_context=world_book_context,
        )

        result = self._invoke_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            scene_id=current_scene.get("id", "default"),
            fallback_context={
                "scene_id": current_scene.get("id", "default"),
                "npc_name": npc.get("name", "对方"),
            },
            is_dialogue=True,
        )
        # NPC 对话输出格式与场景叙事不同（response/emotion vs narrative/choices），
        # 这里做格式归一化：把 response 包装成 narrative + segments + choices
        if not result.get("degraded"):
            result = self._normalize_dialogue_output(result, npc)
        return result

    # ---- 自由输入回应生成（Day 8 新增）----

    def generate_free_input_response(
        self,
        *,
        player_input: str,
        game_state: dict[str, Any],
        current_scene: dict[str, Any],
        npc_cards: dict[str, Any],
        memory: dict[str, Any],
        use_llm_intent: bool = True,
    ) -> dict[str, Any]:
        """处理玩家自由输入，生成回应。

        流程（对齐策划书 3.2.2 节）：
            Step 1: 意图分类（离线关键词 or LLM 精细分类）
            Step 2: OOC 检测
            Step 3: 构建回应 Prompt，调用 LLM 生成叙事

        Args:
            player_input: 玩家自由输入的原始文本
            game_state: GameState v1.0
            current_scene: 当前场景 dict
            npc_cards: 在场 NPC 角色卡 dict
            memory: 记忆上下文 dict
            use_llm_intent: True 用 LLM 分类（更准但慢），False 用离线关键词分类（快）

        Returns:
            符合 docs/agent-io-format.md 的 dict，额外带 intent 和 is_ooc 字段
        """
        # Step 1: 意图分类
        if use_llm_intent and self._llm and not self._llm.is_fake:
            npc_name = ",".join(n.get("name", "") for n in npc_cards.values()) if npc_cards else ""
            intent = self._free_input_processor.classify_intent_llm(
                text=player_input,
                npc_name=npc_name,
                scene_name=current_scene.get("name", ""),
            )
        else:
            intent = self._free_input_processor.classify_intent_offline(player_input)
        logger.info("自由输入意图分类: %s (method=%s, confidence=%.2f)",
                    intent.get("intent"), intent.get("method"), intent.get("confidence", 0))

        # Step 2: OOC 检测
        is_ooc, ooc_reason = self._free_input_processor.detect_ooc(player_input)
        if is_ooc:
            logger.info("OOC 检测命中: %s", ooc_reason)

        # Step 3: 构建回应 Prompt 并调用 LLM
        system_prompt = self._prompt_builder.build_system_prompt(
            world_knowledge=get_all_world_knowledge(),
            current_scene=current_scene,
            npc_cards=npc_cards,
        )
        user_prompt = self._free_input_processor.build_response_prompt(
            player_input=player_input,
            intent=intent,
            game_state=game_state,
            current_scene=current_scene,
            npc_cards=npc_cards,
            memory=memory,
            is_ooc=is_ooc,
            ooc_reason=ooc_reason,
        )

        result = self._invoke_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            scene_id=current_scene.get("id", "default"),
            fallback_context={
                "scene_id": current_scene.get("id", "default"),
                "player_name": game_state.get("player", {}).get("name", "道友"),
            },
        )
        # 附加意图和 OOC 信息供后端使用
        result["intent"] = intent
        result["is_ooc"] = is_ooc
        if is_ooc:
            result["ooc_reason"] = ooc_reason
        return result

    @staticmethod
    def _normalize_dialogue_output(
        parsed: dict[str, Any], npc: dict[str, Any]
    ) -> dict[str, Any]:
        """将 NPC 对话输出归一化为 agent-io-format 兼容结构。

        npc_dialogue.j2 输出: {response, emotion, internal_thought}
        归一化为: {narrative, narrative_segments, available_choices, thought, npc_reactions}
        """
        response_text = parsed.get("response", "")
        emotion = parsed.get("emotion", "")
        internal_thought = parsed.get("internal_thought", "")
        npc_name = npc.get("name", "NPC")

        narrative = response_text
        segments = [
            {"type": "dialogue", "speaker": npc_name, "text": response_text}
        ] if response_text else []

        return {
            "narrative": narrative,
            "narrative_segments": segments,
            "available_choices": [
                {"id": "continue", "text": "继续对话"},
                {"id": "take_leave", "text": "告退"},
            ],
            "free_input_enabled": True,
            "npc_reactions": {
                npc.get("id", "npc"): {
                    "visible_emotion": emotion,
                    "internal_thought": internal_thought,
                }
            },
            "thought": f"NPC 对话生成成功, emotion={emotion}",
        }

    # ---- JSON 提取（对话模式专用，不做字段校验）----

    def _extract_json_only(self, raw_output: str) -> dict[str, Any] | None:
        """从 LLM 输出中提取 JSON，复用 parser 的提取策略但不做字段校验。

        用于 NPC 对话等输出格式与 scene_narrative 不同的场景。
        """
        # 直接 JSON
        result = self._parser._try_direct_json(raw_output)
        if result is not None:
            return result
        # Markdown 代码块
        result = self._parser._try_markdown_block(raw_output)
        if result is not None:
            return result
        # 花括号提取
        result = self._parser._try_brace_extraction(raw_output)
        return result

    # ---- 核心调度：带重试的 LLM 调用 ----

    def _invoke_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        scene_id: str,
        fallback_context: dict[str, Any],
        is_dialogue: bool = False,
    ) -> dict[str, Any]:
        """带重试和降级的 LLM 调用。

        流程（对齐策划书 5.4 节）：
            尝试 LLM 调用 → 解析 → 校验
              ↓ 失败
            重试（最多 max_retries 次，每次重新调用 LLM）
              ↓ 仍失败
            降级响应（返回预设文案）
        """
        last_error: str = ""

        for attempt in range(1, self.max_retries + 1):
            attempt_tag = f"[attempt {attempt}/{self.max_retries}]"
            # 指数退避（第一次不等待）
            if attempt > 1 and self.backoff_base > 0:
                wait_sec = self.backoff_base * (2 ** (attempt - 2))
                logger.info("%s 退避 %.2fs 后重试", attempt_tag, wait_sec)
                time.sleep(wait_sec)
            try:
                start = time.time()
                logger.info("%s 调用 LLM...", attempt_tag)

                raw_output = self._llm.generate(system_prompt, user_prompt)
                elapsed = time.time() - start
                logger.info(
                    "%s LLM 返回 %d 字符, 耗时 %.1fs", attempt_tag, len(raw_output), elapsed
                )

                # 超时检查（虽然不是硬超时，但记录慢调用）
                if elapsed > self.timeout:
                    logger.warning(
                        "%s LLM 耗时 %.1fs 超过阈值 %.1fs", attempt_tag, elapsed, self.timeout
                    )

                # 空输出检查
                if not raw_output or not raw_output.strip():
                    last_error = "empty_llm_output"
                    logger.warning("%s LLM 返回空内容", attempt_tag)
                    continue

                # 解析：对话模式只做 JSON 提取（不校验 available_choices 等字段），
                # 场景叙事模式走完整 parser 校验
                if is_dialogue:
                    parsed = self._extract_json_only(raw_output)
                    if parsed is None:
                        last_error = "dialogue_json_extract_failed"
                        logger.warning(
                            "%s 对话 JSON 提取失败，raw_output 前 100 字: %s",
                            attempt_tag,
                            raw_output[:100],
                        )
                        continue
                else:
                    parsed = self._parser.parse(raw_output)
                    if parsed.get("parse_failed"):
                        last_error = "parse_failed"
                        logger.warning(
                            "%s 解析失败，raw_output 前 100 字: %s",
                            attempt_tag,
                            raw_output[:100],
                        )
                        continue

                # 成功
                logger.info("%s 解析成功", attempt_tag)
                return parsed

            except Exception as e:
                last_error = f"exception: {type(e).__name__}: {e}"
                logger.error("%s LLM 调用异常: %s", attempt_tag, last_error, exc_info=True)
                continue

        # 全部失败：降级
        logger.warning(
            "全部 %d 次重试失败，触发降级。last_error=%s", self.max_retries, last_error
        )
        return self._degraded_response(
            scene_id=scene_id,
            fallback_context=fallback_context,
            error=last_error,
            is_dialogue=is_dialogue,
        )

    # ---- 降级响应 ----

    def _degraded_response(
        self,
        *,
        scene_id: str,
        fallback_context: dict[str, Any],
        error: str,
        is_dialogue: bool = False,
    ) -> dict[str, Any]:
        """降级响应：用预设文案 + 动态填充，保证游戏可运行。

        对齐策划书 5.4 节 _degraded_response 和 docs/agent-io-format.md 第 5.2 节。
        Day 12 会增强为从 content/ 加载场景级预设文案。
        """
        player_name = fallback_context.get("player_name", "道友")
        preset_narrative = get_preset_narrative(scene_id)

        if is_dialogue:
            npc_name = fallback_context.get("npc_name", "对方")
            return {
                "narrative": f"{npc_name}沉默片刻，未置一词。",
                "narrative_segments": [
                    {"type": "narration", "text": f"{npc_name}沉默片刻，未置一词。"}
                ],
                "available_choices": [
                    {"id": "continue", "text": "继续"},
                    {"id": "leave", "text": "告退"},
                ],
                "free_input_enabled": True,
                "thought": f"DEGRADED: npc dialogue fallback, error={error}",
                "degraded": True,
            }

        # 场景叙事降级
        # 用 player_name 做简单模板替换
        narrative = preset_narrative.replace("{player_name}", player_name)
        return {
            "narrative": narrative,
            "narrative_segments": [{"type": "narration", "text": narrative}],
            "available_choices": [
                {"id": "continue", "text": "继续前行"},
                {"id": "observe", "text": "环顾四周"},
            ],
            "free_input_enabled": True,
            "thought": f"DEGRADED: scene narrative fallback, scene={scene_id}, error={error}",
            "degraded": True,
        }


if __name__ == "__main__":
    # 自测入口见 agent/examples/test_day5.py（需加载框架 path）
    print("NarrativeController 自测请运行: python agent/examples/test_day5.py")
