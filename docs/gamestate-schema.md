# GameState Schema v1.0 
## 概述
GameState 是整个游戏的核心状态对象，在前端、后端、Agent 之间传递。所有字段必须严格遵循此文档。

## 结构

### GameState（顶层）
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| session_id | string | "" | 会话唯一标识 |
| turn_count | int | 0 | 当前回合数 |
| player | PlayerState | - | 玩家状态 |
| world | WorldState | - | 世界状态 |
| narrative | string | "" | 当前场景叙事文本（Agent 生成） |
| available_choices | list of choices | [] | 当前可选动作 |
| recent_events | list of EventRecord | [] | 最近事件历史（计划新增） |

### PlayerState
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| name | string | "无名修士" | 玩家角色名 |
| gender | string | "男" | 性别 |
| spiritual_root | string | "无灵根" | 灵根类型 |
| cultivation | int | 0 | 修为值 |
| cultivation_exp | int | 0 | 修为经验值 |
| hp | int | 100 | 生命值 |
| max_hp | int | 100 | 最大生命值 |
| mp | int | 50 | 法力值 |
| max_mp | int | 50 | 最大法力值 |
| spirit_stones | int | 0 | 灵石数量 |
| inventory | list of dict | [] | 背包，每个物品为 {item_id, name, count} |
| skills | list of string | [] | 已学功法 ID 列表 |

### WorldState
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| current_scene_id | string | "start" | 当前场景 ID |
| flags | dict[string, bool] | {} | 剧情标记位 |
| npc_affinity | dict[string, int] | {} | NPC 好感度 |

### FreeInputRecord / EventRecord（待实现）