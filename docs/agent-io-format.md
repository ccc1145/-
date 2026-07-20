# Agent 输入输出格式规范 v1.0

> **版本**: v1.0（Day 3 锁定版）
> **维护人**: 人员C
> **对齐文档**: `docs/gamestate-schema.md` v1.0（人员B锁定版）
> **变更规则**: 锁定后任何变更必须开 PR，受影响模块负责人 Review，全组站会一致同意后才可合并

---

## 1. 概述

本规范定义 Agent 叙事层与后端之间的输入输出契约。

- **输入**：后端 → Agent，包含 GameState + 场景上下文 + 玩家操作 + 记忆 + NPC 角色卡
- **输出**：Agent → 后端，包含叙事文本 + 状态变更 + 下一场景 + 可选操作

Agent 内部流程：`PromptBuilder 渲染模板 → LLMAdapter 调用 LLM → Parser 解析输出`，最终产出符合本规范的 dict。

---

## 2. Agent 输入格式

### 2.1 顶层结构

```json
{
  "request_type": "scene_narrative | npc_dialogue | free_input_response",
  "system_prompt": "你是一位资深的修仙小说作者...",
  "context": {
    "game_state": { /* GameState v1.0 */ },
    "current_scene": { /* 场景元信息，见 2.2 */ },
    "event_context": { /* 事件触发上下文，见 2.3 */ },
    "player_input": { /* 玩家操作，见 2.4 */ },
    "memory": { /* 记忆上下文，见 2.5 */ },
    "npc_cards": { /* NPC 角色卡，见 2.6 */ }
  }
}
```

### 2.2 `current_scene` 场景元信息

由人员D的内容配置提供，非 GameState 字段，作为本次叙事的场景设定。

```json
{
  "id": "trial_grounds",
  "name": "试炼场",
  "description": "试炼场中央立着一块三尺高的测灵石，散发着淡淡的青光",
  "mood": "庄严、期待、一丝紧张",
  "free_input_enabled": true,
  "agent_guidance": {
    "setting_details": ["测灵石呈青白色，表面有天然纹路"],
    "sensory_details": ["石头触感冰凉", "注入灵气后会微微发热"]
  }
}
```

### 2.3 `event_context` 事件触发上下文

后端事件系统已评估完毕、即将应用的状态变更，Agent 需将其"自然融入"叙事。

```json
{
  "event_id": "entrance_trial",
  "triggered_effects": [
    {"type": "modify_attribute", "target": "player.cultivation", "operation": "add", "value": 10},
    {"type": "set_flag", "target": "world.flags.trial_completed", "value": true},
    {"type": "modify_npc_affinity", "target": "world.npc_affinity.master", "value": 3}
  ]
}
```

**`triggered_effects[].target` 必须是 GameState v1.0 中存在的路径**，可用路径见第 4 节。

### 2.4 `player_input` 玩家操作

两种类型：预设选择 / 自由输入。

```json
// 预设选择
{
  "type": "choice",
  "choice_id": "touch_stone",
  "choice_text": "深吸一口气，将手放在测灵石上"
}

// 自由输入
{
  "type": "free_input",
  "text": "长老，弟子有一事不明",
  "interpreted_intent": {
    "intent": "ASK",
    "target": "master",
    "topic": "cultivation",
    "confidence": 0.92
  }
}
```

自由输入的 `interpreted_intent` 由后端意图分类器（调用 Agent `classify_intent`）填充，意图分类体系见策划书 4.5.1 节。

### 2.5 `memory` 记忆上下文

```json
{
  "recent_events": [
    {
      "turn": 1,
      "scene_id": "trial_grounds",
      "narrative": "你将手放在测灵石上...",
      "player_choice": "touch_stone",
      "timestamp": "2026-07-15T10:00:00Z"
    }
  ],
  "dialogue_history": {
    "master": [
      {"player": "弟子拜见长老", "npc": "嗯。既入我青云门，当恪守门规。"}
    ]
  },
  "world_knowledge": [
    "青云门建派三百年",
    "测灵石用于检测灵根属性"
  ]
}
```

- `recent_events`：最近 3-5 条事件记录（截断保留）
- `dialogue_history`：各 NPC 的最近对话（每 NPC 保留 5 轮）
- `world_knowledge`：硬编码的 MVP 世界观知识条目

### 2.6 `npc_cards` NPC 角色卡

由人员D的内容配置提供，结构见 `content/npcs/*.yaml`。仅包含当前场景可能出场的 NPC。

```json
{
  "master": {
    "npc_id": "master",
    "name": "玄清真人",
    "description": "青云门长老，金丹期修士，性格严厉但护短",
    "personality": {
      "traits": ["严厉", "护短", "重规矩"],
      "speaking_style": "言简意赅，喜欢用古语训诫弟子",
      "values": ["门派荣誉", "修炼根基"],
      "dislikes": ["懒惰", "顶撞师长"],
      "emotional_range": ["平静", "严肃", "赞许", "愤怒"]
    },
    "current_affinity": 5,
    "dialogue_examples": [
      {"context": "玩家初次见面", "user": "弟子拜见长老", "response": "嗯。你既入我青云门，当恪守门规。"}
    ]
  }
}
```

**注意**：`current_affinity` 是快照值，与 `game_state.world.npc_affinity.master` 保持一致；后端组装 Prompt 时负责同步。

---

## 3. Agent 输出格式

### 3.1 顶层结构

```json
{
  "narrative": "你将手放在测灵石上，一股温热的气息顺着手臂流入体内...",
  "narrative_segments": [
    {"type": "narration", "text": "你将手放在测灵石上..."},
    {"type": "dialogue", "speaker": "玄清真人", "text": "嗯，火灵根。"}
  ],
  "state_changes": {
    "player.cultivation": 10,
    "world.flags.trial_completed": true,
    "world.npc_affinity.master": 3
  },
  "next_scene_id": "trial_result",
  "available_choices": [
    {"id": "express_gratitude", "text": "弟子拜谢长老"},
    {"id": "stay_silent", "text": "默默退到一旁"}
  ],
  "free_input_enabled": true,
  "npc_reactions": {
    "master": {
      "visible_emotion": "满意",
      "internal_thought": "此子灵根尚可，但需观察心性"
    }
  },
  "thought": "玩家选择测灵石，触发入门试炼..."
}
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `narrative` | string | 二选一 | 完整叙事文本（200-400 字），与 `narrative_segments` 至少提供一个 |
| `narrative_segments` | list | 二选一 | 分段叙事（用于打字机效果），每段含 `type`/`text`，dialogue 段需含 `speaker` |
| `state_changes` | object | 否 | Agent 建议的状态变更（路径→值），最终是否应用由后端事件系统决定 |
| `next_scene_id` | string | 否 | 建议的下一场景 ID，最终是否切换由后端事件系统决定 |
| `available_choices` | list | 是 | 2-4 个可选操作，每个含 `id`/`text` |
| `free_input_enabled` | bool | 否 | 当前场景是否允许自由输入，默认 true |
| `npc_reactions` | object | 否 | NPC 的可见情绪与内心想法（内心想法调试用，不展示给玩家） |
| `thought` | string | 否 | Agent 的推理过程（调试用，对应 `agent_thought` 字段） |

### 3.3 `narrative_segments` 段类型

| `type` | 必填字段 | 说明 |
|---|---|---|
| `narration` | `text` | 旁白叙述 |
| `dialogue` | `text`, `speaker` | NPC 台词 |
| `action` | `text` | 玩家动作描述（预留，MVP 可不区分） |

---

## 4. `state_changes` 路径白名单

`state_changes` 中的 key 必须是 GameState v1.0 中存在的路径。**合法路径清单**：

### 4.1 玩家属性（`player.*`）

| 路径 | 类型 | 说明 |
|---|---|---|
| `player.cultivation` | int | 修为值 |
| `player.cultivation_exp` | int | 修为经验 |
| `player.hp` | int | 当前生命值 |
| `player.max_hp` | int | 最大生命值 |
| `player.mp` | int | 当前法力值 |
| `player.max_mp` | int | 最大法力值 |
| `player.spirit_stones` | int | 灵石数量 |

> **注意**：`player.name` / `player.gender` / `player.spiritual_root` 为角色身份字段，不可通过 `state_changes` 修改。

### 4.2 背包与功法（追加语义）

| 路径 | 语义 | 示例值 |
|---|---|---|
| `player.inventory` | 追加物品 | `{"item_id": "qi_pill", "name": "聚气丹", "count": 1}` |
| `player.skills` | 追加功法 ID | `"qingyun_jue"` |

后端收到追加语义时，将值 append 到对应 list，而非覆盖。

### 4.3 世界状态（`world.*`）

| 路径 | 类型 | 说明 |
|---|---|---|
| `world.current_scene_id` | string | 当前场景 ID |
| `world.flags.<flag_name>` | bool | 剧情标记位（自动创建不存在的 flag） |
| `world.npc_affinity.<npc_id>` | int | NPC 好感度（增量语义，值可为负） |

> **v1.0 变更提醒**：好感度路径从草案的 `npcs.<id>.affinity` 改为 `world.npc_affinity.<id>`，请在 `state_changes` 中使用新路径。

---

## 5. 校验规则

### 5.1 必填校验

- `narrative` 和 `narrative_segments` **至少提供一个**，否则视为解析失败
- `available_choices` 必填，长度 1-4，每个 choice 必须含 `id` 和 `text`
- `narrative_segments` 中 `type=dialogue` 的段必须含 `speaker`

### 5.2 路径校验

- `state_changes` 中的 key 必须命中第 4 节白名单
- 非法路径由后端丢弃并记录 warning，不抛错（保证游戏不卡）

### 5.3 类型校验

- 数值字段（cultivation/hp/mp/spirit_stones/affinity）必须为 int
- 布尔字段（flags）必须为 bool
- 字符串字段（next_scene_id/scene_id）必须为 string

### 5.4 解析失败处理

LLM 输出无法解析为合法 JSON 时，Parser 重试 3 次后降级，降级输出格式：

```json
{
  "narrative": "（叙事生成中，请稍候...）",
  "narrative_segments": [{"type": "narration", "text": "（叙事生成中，请稍候...）"}],
  "state_changes": {},
  "available_choices": [
    {"id": "continue", "text": "继续"},
    {"id": "retry", "text": "重新尝试"}
  ],
  "free_input_enabled": true,
  "thought": "DEGRADED: parser fallback",
  "degraded": true,
  "parse_failed": true
}
```

---

## 6. 请求类型与模板映射

| `request_type` | 用途 | 渲染模板 | Day |
|---|---|---|---|
| `scene_narrative` | 场景叙事（默认） | `scene_narrative.j2` | Day 3 |
| `npc_dialogue` | NPC 动态对话 | `npc_dialogue.j2` | Day 4 |
| `free_input_response` | 自由输入回应 | `free_input_response.j2` | Day 8 |

---

## 7. 版本历史

| 版本 | 日期 | 变更说明 | 维护人 |
|---|---|---|---|
| v1.0 | 2026-07-15 | Day 3 锁定版。对齐 GameState v1.0：`spiritual_root` 改字符串、删除 `realm`/`attributes`、好感度并入 `world.npc_affinity`、新增 hp/mp/spirit_stones/skills 路径 | 人员C |
