# Agent IO 格式规范 v1.0

> **状态**：已锁定（基于 docs/gamestate-schema.md v1.0）
> **维护人**：人员C（Agent 工程师）
> **对接人**：人员B（后端工程师，负责 Agent 桥接层）
> **变更原则**：任何字段变更必须走 PR + 全组 Review

---

## 一、概述

Agent 层负责生成游戏叙事内容，输入为 `AgentRequest`，输出为 `AgentResponse`。

**设计原则**：
1. GameState 严格遵循 [docs/gamestate-schema.md v1.0](./gamestate-schema.md)
2. 场景详细信息（name/description/mood）和 NPC 角色卡作为独立上下文传入，由后端从 `content/` 查询得到
3. Agent 输出统一为 JSON，由 Parser 解析后供后端使用
4. 失败时返回降级响应（带 `degraded: true` 标记），保证游戏可运行

---

## 二、输入格式（AgentRequest）

```json
{
  "request_type": "scene_narrative | npc_dialogue | free_input_response",
  "system_prompt": "（由 PromptBuilder 生成的系统提示，无需后端构造）",
  "context": {
    "game_state": { ... },
    "current_scene": { ... },
    "npc_cards": { ... },
    "player_input": { ... },
    "event_context": { ... },
    "memory": { ... },
    "world_knowledge": [ ... ]
  }
}
```

> **实现说明**：后端只需把 `context` 传给 `NarrativeController` 的对应方法，`system_prompt` 由 Agent 层内部通过 `PromptBuilder` 生成。后端无需关心 Prompt 拼接。

### 2.1 game_state（GameState v1.0）

严格遵循 [docs/gamestate-schema.md v1.0](./gamestate-schema.md)。关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | string | 会话唯一标识 |
| `turn_count` | int | 当前回合数 |
| `player` | PlayerState | 玩家状态（见下表） |
| `world` | WorldState | 世界状态（见下表） |
| `narrative` | string | 当前场景叙事文本（上一轮 Agent 生成） |
| `available_choices` | list | 当前可选动作 |
| `recent_events` | list[EventRecord] | 最近事件历史 |

**PlayerState**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 玩家角色名 |
| `gender` | string | 性别 |
| `spiritual_root` | string | 灵根类型（如 "火灵根"，v1.0 改为字符串） |
| `cultivation` | int | 修为值 |
| `cultivation_exp` | int | 修为经验值 |
| `hp` / `max_hp` | int | 生命值 / 上限 |
| `mp` / `max_mp` | int | 法力值 / 上限 |
| `spirit_stones` | int | 灵石数量 |
| `inventory` | list[{item_id, name, count}] | 背包 |
| `skills` | list[string] | 已学功法 ID 列表 |

**WorldState**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `current_scene_id` | string | 当前场景 ID |
| `flags` | dict[string, bool] | 剧情标记位 |
| `npc_affinity` | dict[string, int] | NPC 好感度（key 是 NPC ID） |

**示例**：
```json
{
  "session_id": "session-001",
  "turn_count": 3,
  "player": {
    "name": "李逍遥",
    "gender": "男",
    "spiritual_root": "火灵根",
    "cultivation": 10,
    "cultivation_exp": 0,
    "hp": 100, "max_hp": 100,
    "mp": 50, "max_mp": 50,
    "spirit_stones": 5,
    "inventory": [
      {"item_id": "qi_pill", "name": "聚气丹", "count": 2}
    ],
    "skills": ["basic_sword"]
  },
  "world": {
    "current_scene_id": "trial_grounds",
    "flags": {"met_master": true},
    "npc_affinity": {"master": 5}
  },
  "narrative": "（上一轮叙事文本）",
  "available_choices": [],
  "recent_events": []
}
```

### 2.2 current_scene（场景详细信息）

后端根据 `game_state.world.current_scene_id` 从 `content/scenes/` 查询得到，传给 Agent 用于 Prompt 注入。

```json
{
  "id": "trial_grounds",
  "name": "试炼场",
  "description": "试炼场中央立着一块古朴的测灵石，四周环绕着淡淡的灵气。",
  "mood": "庄严、期待"
}
```

### 2.3 npc_cards（NPC 角色卡详细信息）

后端根据 `game_state.world.npc_affinity` 的 key 从 `content/npcs/` 查询得到。`current_affinity` 应与 `game_state.world.npc_affinity[npc_id]` 一致。

```json
{
  "master": {
    "id": "master",
    "name": "玄清真人",
    "personality": {
      "traits": ["严厉", "护短"],
      "values": ["门派荣誉", "弟子心性"],
      "dislikes": ["浮夸", "不敬师长"],
      "speaking_style": "言简意赅，偶尔带文言"
    },
    "current_affinity": 5
  }
}
```

### 2.4 player_input（玩家操作）

两种类型：

**选项选择**：
```json
{"type": "choice", "value": "touch_stone", "choice_text": "触摸测灵石"}
```

**自由输入**：
```json
{"type": "free_input", "text": "师父，弟子的灵根如何？适合修炼什么功法？"}
```

### 2.5 event_context（事件上下文）

```json
{
  "event_id": "entrance_trial",
  "triggered_effects": [
    {"type": "modify_attribute", "target": "player.cultivation", "value": 10}
  ]
}
```

### 2.6 memory（记忆上下文）

```json
{
  "recent_events": [
    {"turn": 1, "narrative": "上一轮叙事文本前 50 字..."}
  ],
  "dialogue_history": {
    "master": ["玩家：拜见师父", "玄清真人：嗯，来了。"]
  }
}
```

### 2.7 world_knowledge（世界观知识）

字符串列表，由 Agent 层内部维护（当前硬编码在 `agent/src/world_knowledge.py`，Day 10 后从 `content/world/` 加载）。

```json
[
  "修仙第一步是练气，将天地灵气引入体内，淬炼经脉。",
  "青云门建派三百年，是修仙界四大宗门之一。"
]
```

---

## 三、输出格式（AgentResponse）

### 3.1 scene_narrative 输出

```json
{
  "narrative": "完整的叙事文本（200-400 字）",
  "narrative_segments": [
    {"type": "narration", "text": "旁白片段"},
    {"type": "dialogue", "speaker": "玄清真人", "text": "NPC台词"}
  ],
  "available_choices": [
    {"id": "choice_continue", "text": "继续前行"},
    {"id": "choice_observe", "text": "环顾四周"}
  ],
  "free_input_enabled": true,
  "thought": "（可选）Agent 内部思考，用于调试"
}
```

| 字段 | 类型 | MVP 必需 | 说明 |
|------|------|----------|------|
| `narrative` | string | ✅ | 完整叙事文本 |
| `narrative_segments` | list[Segment] | ✅ | 叙事分段（含 dialogue 类型） |
| `available_choices` | list[Choice] | ✅ | 下一步选项（1-4 个） |
| `free_input_enabled` | bool | ✅ | 是否允许自由输入 |
| `thought` | string | ⚠️ 可选 | 调试用思考过程 |
| `state_changes` | list | ⚠️ 可选 | Agent 建议的状态变化（MVP 由后端事件系统处理） |
| `npc_reactions` | dict | ⚠️ 可选 | NPC 反应详情 |

**Segment 结构**：
```json
{"type": "narration | dialogue", "text": "片段文本", "speaker": "NPC名（仅 dialogue）"}
```

**Choice 结构**：
```json
{"id": "choice_id", "text": "选项文字"}
```

### 3.2 npc_dialogue 输出（归一化后）

NPC 对话 LLM 原始输出为 `{response, emotion, internal_thought}`，由 `NarrativeController._normalize_dialogue_output()` 归一化为与 scene_narrative 兼容的结构：

```json
{
  "narrative": "NPC 的回应文本",
  "narrative_segments": [
    {"type": "dialogue", "speaker": "玄清真人", "text": "回应文本"}
  ],
  "available_choices": [
    {"id": "continue", "text": "继续对话"},
    {"id": "take_leave", "text": "告退"}
  ],
  "free_input_enabled": true,
  "npc_reactions": {
    "master": {
      "visible_emotion": "平静",
      "internal_thought": "（NPC 内心活动）"
    }
  },
  "thought": "NPC 对话生成成功, emotion=平静"
}
```

### 3.3 free_input_response 输出

自由输入回应复用 scene_narrative 的输出格式。Agent 通过 `request_type=scene_narrative` 处理自由输入（`player_input.type == "free_input"`），生成的叙事中会包含对自由输入的回应。

---

## 四、字段校验规则

Parser（`agent/src/parser.py`）对 LLM 输出做以下校验和补全：

| 规则 | 处理方式 |
|------|----------|
| `narrative` 缺失或为空 | 标记 `parse_failed: true`，返回降级响应 |
| `narrative_segments` 缺失 | 自动用 `[{"type": "narration", "text": narrative}]` 补全 |
| `available_choices` 缺失 | 自动补兜底选项 `[{"id": "continue", "text": "继续"}]` |
| `available_choices` 超过 4 个 | 截断保留前 4 个 |
| `dialogue` 类型 segment 缺 `speaker` | 自动清理该 segment |
| `free_input_enabled` 缺失 | 默认 `true` |
| JSON 解析失败 | 尝试 3 种策略：直接解析 → Markdown 代码块提取 → 花括号提取 |

---

## 五、降级机制

### 5.1 触发条件

以下任一情况触发降级：
1. LLM 调用异常（网络错误、API 错误）
2. LLM 返回空内容
3. 3 次重试后解析仍失败

### 5.2 降级响应格式

```json
{
  "narrative": "（预设降级文案，从 world_knowledge.SCENE_PRESET_NARRATIVES 加载）",
  "narrative_segments": [
    {"type": "narration", "text": "（同 narrative）"}
  ],
  "available_choices": [
    {"id": "continue", "text": "继续前行"},
    {"id": "observe", "text": "环顾四周"}
  ],
  "free_input_enabled": true,
  "thought": "DEGRADED: scene narrative fallback, scene=trial_grounds, error=parse_failed",
  "degraded": true
}
```

**降级标记**：`degraded: true` 表示此响应为降级产生，后端可据此决定是否记录日志或提示用户。

### 5.3 重试策略

```
LLM 调用 → 解析 → 校验
  ↓ 失败
重试 1（重新调用 LLM）
  ↓ 失败
重试 2
  ↓ 失败
重试 3
  ↓ 失败
降级响应（返回预设文案）
```

---

## 六、request_type 路由

| request_type | 调用方法 | 适用场景 |
|--------------|----------|----------|
| `scene_narrative` | `NarrativeController.generate_scene_narrative()` | 玩家选择/自由输入后的场景叙事 |
| `npc_dialogue` | `NarrativeController.generate_npc_dialogue()` | 与 NPC 对话 |
| `free_input_response` | 复用 `generate_scene_narrative()` | 自由输入回应（Day 8 扩展独立处理器） |

---

## 七、JSON Schema（供后端校验用）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AgentResponse",
  "type": "object",
  "required": ["narrative", "narrative_segments", "available_choices"],
  "properties": {
    "narrative": {"type": "string", "minLength": 1},
    "narrative_segments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "text"],
        "properties": {
          "type": {"type": "string", "enum": ["narration", "dialogue"]},
          "text": {"type": "string"},
          "speaker": {"type": "string"}
        }
      }
    },
    "available_choices": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["id", "text"],
        "properties": {
          "id": {"type": "string"},
          "text": {"type": "string"}
        }
      }
    },
    "free_input_enabled": {"type": "boolean", "default": true},
    "thought": {"type": "string"},
    "degraded": {"type": "boolean", "default": false},
    "npc_reactions": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "visible_emotion": {"type": "string"},
          "internal_thought": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 八、Mock 输出（供后端开发用）

见 `backend/tests/mock_agent.py`，提供三种 request_type 的 Mock 响应，后端开发桥接层时无需等真实 Agent。

调用方式：
```python
from backend.tests.mock_agent import get_mock_agent_output
mock_response = get_mock_agent_output("scene_narrative")
```

---

## 九、变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|----------|--------|
| v0.1 | Day 2 | 初稿，定义基本输入输出结构 | 人员C |
| v1.0 | Day 5 | 对齐 gamestate-schema.md v1.0；补充 NPC 对话归一化、降级机制、JSON Schema、Mock 调用方式 | 人员C |
