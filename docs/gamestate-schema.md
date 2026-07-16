# GameState Schema v1.0（锁定版）

## 1. 概述

`GameState` 是修仙模拟器在前端、后端和 Agent 之间传递的权威游戏状态。

- 后端实现基准：`backend/app/schemas/game_state.py`
- 前端类型映射：`frontend/src/types/game.ts`
- 字段命名统一使用 `snake_case`
- 未经契约变更 PR，不得直接增加、删除或重命名字段

本文档描述当前代码实际使用的 v1.0 结构。后端 Pydantic 模型是运行时校验的最终依据。

## 2. 类型映射

| Schema 类型 | Python | TypeScript |
|---|---|---|
| string | `str` | `string` |
| integer | `int` | `number` |
| boolean | `bool` | `boolean` |
| nullable integer | `Optional[int]` | `number \| null` |
| nullable string | `Optional[str]` | `string \| null` |
| list | `List[T]` | `T[]` |
| dictionary | `Dict[str, T]` | `Record<string, T>` |

## 3. GameState

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `session_id` | string | `""` | 会话唯一标识 |
| `current_scene_id` | string | `"start"` | 当前场景 ID |
| `turn_count` | integer | `0` | 已处理的玩家行动回合数 |
| `player` | `PlayerState` | 默认对象 | 玩家状态 |
| `npcs` | `Record<string, NPCState>` | `{}` | NPC 状态，以 NPC ID 为键 |
| `world` | `WorldState` | 默认对象 | 世界状态 |
| `recent_events` | `EventRecord[]` | `[]` | 最近的事件记录 |
| `free_input_history` | `FreeInputRecord[]` | `[]` | 玩家自由输入历史 |

示例：

```json
{
  "session_id": "sess_abc123",
  "current_scene_id": "trial_grounds",
  "turn_count": 1,
  "player": {},
  "npcs": {},
  "world": {},
  "recent_events": [],
  "free_input_history": []
}
```

## 4. PlayerState

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `name` | string | `"无名修士"` | 玩家姓名 |
| `cultivation` | integer | `0` | 当前修为值 |
| `realm` | `Realm` | 默认对象 | 当前境界 |
| `spirit_root` | `SpiritRoot` | 默认对象 | 灵根信息 |
| `attributes` | `PlayerAttributes` | 默认对象 | 基础属性 |
| `inventory` | `InventoryItem[]` | `[]` | 玩家背包 |
| `hp` | nullable integer | `100` | 当前生命值 |
| `max_hp` | nullable integer | `100` | 最大生命值 |
| `mp` | nullable integer | `50` | 当前法力值 |
| `max_mp` | nullable integer | `50` | 最大法力值 |
| `spirit_stones` | integer | `0` | 灵石数量 |
| `skills` | `string[]` | `[]` | 已掌握的功法或技能 ID |

`hp`、`max_hp`、`mp`、`max_mp` 在后端允许为 `null`，前端必须按 `number | null` 处理。

### 4.1 Realm

| 字段 | 类型 | 默认值 | 约束 |
|---|---|---|---|
| `major` | string | `"练气"` | `"练气"` 或 `"筑基"` |
| `minor` | integer | `1` | 当前小境界层数 |

### 4.2 SpiritRoot

| 字段 | 类型 | 默认值 | 约束 |
|---|---|---|---|
| `type` | string | `"杂灵根"` | `"金"`、`"木"`、`"水"`、`"火"`、`"土"` 或 `"杂灵根"` |
| `quality` | integer | `1` | 灵根品质 |

### 4.3 PlayerAttributes

| 字段 | 类型 | 默认值 |
|---|---|---|
| `strength` | integer | `5` |
| `agility` | integer | `5` |
| `intelligence` | integer | `5` |
| `perception` | integer | `5` |

## 5. InventoryItem

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `item_id` | string | 无 | 物品 ID |
| `name` | string | 无 | 显示名称 |
| `quantity` | integer | 无 | 数量 |
| `effects` | `ItemEffect[]` | `[]` | 物品效果 |

### 5.1 ItemEffect

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `type` | string | 无 | 效果类型 |
| `value` | nullable integer | `null` | 效果数值 |
| `description` | nullable string | `null` | 效果说明 |

## 6. NPCState

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | string | 无 | NPC ID |
| `name` | string | 无 | NPC 名称 |
| `affinity` | integer | `0` | 对玩家的好感度 |
| `location` | string | `""` | NPC 当前地点 |
| `known_info` | `string[]` | `[]` | 玩家已知的 NPC 信息 |
| `dialogue_history` | `string[]` | `[]` | 最近对话历史 |

## 7. WorldState

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `current_location` | string | `"青云门山门"` | 玩家当前地点 |
| `time` | `WorldTime` | 默认对象 | 当前时间 |
| `flags` | `Record<string, boolean>` | `{}` | 剧情标记 |

### 7.1 WorldTime

| 字段 | 类型 | 默认值 | 约束 |
|---|---|---|---|
| `day` | integer | `1` | 游戏内天数 |
| `period` | string | `"上午"` | `"早晨"`、`"上午"`、`"下午"`、`"傍晚"` 或 `"夜晚"` |

## 8. EventRecord

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `turn` | integer | 无 | 事件发生回合 |
| `scene_id` | string | 无 | 事件发生场景 |
| `narrative` | string | 无 | 事件叙事 |
| `player_choice` | string | 无 | 玩家选择或输入 |
| `state_changes` | `Record<string, unknown>` | `{}` | 权威状态变化摘要 |
| `timestamp` | string | `""` | ISO 8601 时间字符串 |

## 9. FreeInputRecord

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `turn` | integer | 无 | 输入发生回合 |
| `input_text` | string | 无 | 玩家原始输入 |
| `interpreted_intent` | string | 无 | Agent 或规则识别出的意图 |
| `narrative_response` | string | 无 | 对应叙事响应 |
| `timestamp` | string | `""` | ISO 8601 时间字符串 |

## 10. 完整示例

```json
{
  "session_id": "sess_abc123",
  "current_scene_id": "start",
  "turn_count": 0,
  "player": {
    "name": "周泠锋",
    "cultivation": 0,
    "realm": {
      "major": "练气",
      "minor": 1
    },
    "spirit_root": {
      "type": "水",
      "quality": 7
    },
    "attributes": {
      "strength": 5,
      "agility": 5,
      "intelligence": 5,
      "perception": 5
    },
    "inventory": [],
    "hp": 100,
    "max_hp": 100,
    "mp": 50,
    "max_mp": 50,
    "spirit_stones": 0,
    "skills": []
  },
  "npcs": {
    "master": {
      "id": "master",
      "name": "玄清真人",
      "affinity": 0,
      "location": "试炼场",
      "known_info": [],
      "dialogue_history": []
    }
  },
  "world": {
    "current_location": "试炼场",
    "time": {
      "day": 1,
      "period": "上午"
    },
    "flags": {}
  },
  "recent_events": [],
  "free_input_history": []
}
```

## 11. 变更规则

1. 修改后端 `GameState` 或任何嵌套模型时，必须在同一个 PR 中更新本文档和 `frontend/src/types/game.ts`。
2. 删除或重命名字段属于破坏性变更，必须提升契约版本。
3. Agent 只能读取 GameState 并生成叙事，不得自行修改权威状态。
4. `GameEngine` 是游戏状态变化的唯一权威来源。
