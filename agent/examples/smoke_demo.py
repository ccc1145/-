"""最小冒烟 demo：Mock GameState -> 渲染 Prompt -> 调 LLM -> 打印结果。

目标：验证 Agent 端到端链路可用（模板能渲染、LLM 能调用、字符串能拿到）。

运行方式：
    cd d:\\实训\\xiuxian-simulator\\agent

# 1) 离线模式（FakeLLM，免费，无 API Key）
    python examples/smoke_demo.py

# 2) 真实 LLM 模式（小米 MiMo，OpenAI 兼容接口）
    # Windows PowerShell:
    $env:MIMO_API_KEY="你的key"
    python examples/smoke_demo.py --real

    # Windows CMD:
    set MIMO_API_KEY=你的key
    python examples/smoke_demo.py --real
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---- 开发期 path 处理（正式项目应 pip install -e . 两个包，就不用这段了）----
AGENT_ROOT = Path(__file__).resolve().parents[1]          # .../xiuxian-simulator/agent
PROJECT_ROOT = AGENT_ROOT.parent                          # .../xiuxian-simulator（仓库根，含 ai_agent_framework）
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"
sys.path.insert(0, str(FRAMEWORK_SRC))   # 让 ai_agent_framework 可 import
sys.path.insert(0, str(AGENT_ROOT / "src"))  # 让 agent 自身模块可 import

from ai_agent_framework.config.settings import LLMConfig  # noqa: E402

from llm_adapter import NarrativeLLMAdapter  # noqa: E402
from prompt_builder import PromptBuilder  # noqa: E402


# ---- MiMo 接口配置（小米开放平台，OpenAI 兼容）----
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5"   # 平台返回的模型 id 是全小写；更强的还有 "mimo-v2.5-pro"


def _build_llm_config(use_real: bool) -> LLMConfig:
    """根据命令行参数构造 LLM 配置。"""
    if not use_real:
        return LLMConfig(provider="fake", model="fake")

    api_key = os.environ.get("MIMO_API_KEY")
    if not api_key:
        print("[错误] 真实 LLM 模式需要环境变量 MIMO_API_KEY")
        print("       PowerShell: $env:MIMO_API_KEY='你的key'")
        print("       CMD:        set MIMO_API_KEY=你的key")
        sys.exit(1)

    return LLMConfig(
        provider="openai",
        model=MIMO_MODEL,
        api_key=api_key,
        base_url=MIMO_BASE_URL,
        temperature=0.8,   # 叙事生成用稍高温度，文本更有变化
        # MiMo 是推理模型，会先消耗 token "思考"（reasoning_tokens）再输出正文
        # 思考通常占 500-1500 token，叙事正文约 800-1200 token，所以总额度要给足
        max_tokens=4000,
    )


# ---- Mock 数据（结构对齐策划书 4.1 GameState 与 4.3 Agent 输入）----
MOCK_GAME_STATE = {
    "player": {
        "name": "李逍遥",
        "cultivation": 0,
        "realm": {"major": "练气", "minor": 1},
        "spirit_root": {"type": "火", "quality": 7},
    }
}

MOCK_SCENE = {
    "name": "试炼场",
    "description": "试炼场中央立着一块三尺高的测灵石，散发着淡淡的青光",
    "mood": "庄严、期待、一丝紧张",
}

MOCK_NPC_CARDS = {
    "master": {
        "name": "玄清真人",
        "personality": {
            "traits": ["严厉", "护短", "重规矩"],
            "speaking_style": "言简意赅，喜欢用古语训诫弟子",
        },
        "current_affinity": 0,
    }
}

MOCK_PLAYER_INPUT = {
    "type": "choice",
    "choice_text": "深吸一口气，将手放在测灵石上",
}

MOCK_EVENT_CONTEXT = {
    "triggered_effects": [
        {"target": "player.cultivation", "value": 10}
    ]
}

MOCK_MEMORY = {
    "recent_events": []
}


def main() -> int:
    use_real = "--real" in sys.argv
    mode_label = "真实 LLM (MiMo)" if use_real else "FakeLLM (离线)"

    # 1. 构造 LLM 适配器
    adapter = NarrativeLLMAdapter(_build_llm_config(use_real))
    builder = PromptBuilder()

    # 2. 渲染 Prompt
    system_prompt = builder.build_system_prompt(
        world_knowledge=["青云门建派三百年", "测灵石用于检测灵根属性"],
        current_scene=MOCK_SCENE,
        npc_cards=MOCK_NPC_CARDS,
    )
    user_prompt = builder.build_scene_narrative_prompt(
        game_state=MOCK_GAME_STATE,
        player_input=MOCK_PLAYER_INPUT,
        event_context=MOCK_EVENT_CONTEXT,
        memory=MOCK_MEMORY,
    )

    print("=" * 60)
    print(f"【运行模式】{mode_label}")
    print("=" * 60)

    # 真实 LLM 模式下，Prompt 太长就不打印了，直接看结果
    if not use_real:
        print("\n" + "=" * 60)
        print("【System Prompt】")
        print("=" * 60)
        print(system_prompt)

        print("\n" + "=" * 60)
        print("【User Prompt】")
        print("=" * 60)
        print(user_prompt)

    # 3. 调用 LLM（用 adapter.generate，内部已处理推理模型字段兜底）
    print("\n" + "=" * 60)
    print(f"【LLM 输出】（{mode_label}）")
    print("=" * 60)
    try:
        output = adapter.generate(system_prompt, user_prompt)
    except Exception as e:
        print(f"[LLM 调用失败] {type(e).__name__}: {e}")
        print("\n排查建议：")
        print("  1. 检查 MIMO_API_KEY 是否正确")
        print("  2. 检查 base_url (https://api.xiaomimimo.com/v1) 是否可达")
        print("  3. 检查 model 名 (mimo-v2.5) 是否在平台上存在")
        return 1

    if not output:
        print("[警告] LLM 返回空内容（推理模型可能思考超时或被截断），请重试一次。")
        return 1

    print(output)

    print("\n" + "=" * 60)
    print("[链路验证] 模板渲染 ✓  | LLM 调用 ✓  | 文本返回 ✓")
    print("=" * 60)
    if use_real:
        print("[观察要点]")
        print("  1. 输出是不是 JSON 格式（narrative + narrative_segments + available_choices）")
        print("  2. 叙事风格是不是古风修仙（没有现代网络用语）")
        print("  3. NPC 对话（玄清真人）是不是符合'严厉、言简意赅'的性格")
        print("  4. 修为+10 这个状态变化是不是自然融入叙事（不是'你获得10修为'）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
