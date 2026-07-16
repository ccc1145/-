# AGENTS.md — 修仙模拟器项目

> 本文档为 AI 助手提供项目上下文，确保每次协作都能准确理解项目目标、当前角色分工和内容规范。

---

## 项目概述

**项目名称**：修仙模拟器（Text Adventure Cultivation Simulator）

**项目类型**：AI 驱动的文字冒险游戏（Web 应用）

**技术栈**：前端 + 后端 + LLM Agent 叙事引擎

**开发周期**：3 周（2026年7月）

**团队规模**：4 人

**代码仓库**：GitLab `https://gitlab.omniedu.com/root/4yXBj6y6NWkbw.git`

---

## 当前用户角色

**人员 D：世界观设计师 + 内容工程师**

负责修仙世界观设定、内容配置（NPC、事件、物品）的编写与维护，确保所有内容符合 JSON Schema 规范并通过校验。

**关键文件**：
- 角色分工文档：`修仙模拟器-角色分工文档.md`
- 开发计划：`修仙模拟器-三周开发计划与分工-v2.md`
- 世界观设定：`九洲修仙世界观设定.md`

---

## 内容系统架构

### 事件系统双层架构（v2.0）

事件分为三种类型，充分利用 LLM 叙事能力：

| 类型 | 驱动者 | 玩家自由度 | 叙事方式 | 示例 |
|------|--------|-----------|---------|------|
| **大事件（major）** | 世界状态/时间线 | 有限（2-4 个关键抉择） | 预设场景 + Agent 渲染 | 入门试炼、拜师、门派大比 |
| **小事件（minor）** | 玩家行为 + AI 判断 | 完全自由输入 | Agent 全权驱动 | 采药、师兄求助、宿敌切磋 |
| **日常（daily）** | 玩家自主 | 完全自由 | 自由探索 + Agent 叙事 | 移动、交谈、修炼、炼丹 |

**核心原则**：大事件管骨架（时代趋势不可逆），小事件填血肉（高度自由），自由探索是日常，**世界书供弹药**（动态知识注入 Agent Prompt）。

详见 `content/事件系统设计-v2.md`。

### 世界书系统（World Book）

借鉴 SillyTavern Lorebook 的动态知识注入机制：

- 世界观知识拆成**知识碎片（Entry）**，每个碎片有**触发关键词（Keys）**
- 引擎扫描当前对话/场景，匹配到关键词后，将对应知识注入 Agent Prompt
- **只注入相关的知识**，不相关的知识不浪费 Token
- 支持生命周期管理：`sticky`（持续生效）、`cooldown`（冷却）、`probability`（概率触发）

**解决的问题**：小事件和自由探索中，Agent 需要大量世界知识来生成合理叙事。世界书按需注入，Agent 始终获得"恰到好处"的知识支持。

### 目录结构

```
content/
├── schema/                        # JSON Schema 定义（内容规范，锁定后变更需 PR）
│   ├── npc.schema.json            #   NPC 角色卡结构
│   ├── event.schema.json          #   事件配置结构（支持 major/minor/daily）
│   ├── item.schema.json           #   物品配置结构
│   └── world_book.schema.json     #   世界书知识库结构
├── npcs/                          # NPC 角色卡（YAML 格式）——暂空，待配
├── events/
│   ├── major/                     # 大事件（主线剧情）
│   │   ├── 00_awakening_selection.yaml  #   启灵与择宗（通用开局流程）
│   └── minor/                     # 小事件（支线/随机触发）——待重新设计
├── world_books/                   # 世界书知识库（JSON 格式）
│   ├── zhongzhou_geography.json   #   中洲地理志
│   ├── zhongzhou_politics.json    #   中洲王朝志
│   ├── jiuzhou_geography.json     #   九洲地理
│   ├── sect_lore.json             #   九洲宗门录（中洲卷详订）
│   ├── menfa_lore.json            #   中洲门阀志
│   ├── suizhu_history.json        #   岁主与历史
│   ├── xuanqing_sect.json         #   玄清宗专属知识
│   ├── shenwu_sect.json           #   神武门专属知识
│   ├── fulong_sect.json           #   扶龙宫专属知识
│   ├── hongchen_sect.json         #   红尘阁专属知识
│   ├── cultivation_system.json    #   修炼体系知识
├── items/                         # 物品配置（YAML 格式）
│   └── basic_items.yaml
├── free_exploration.yaml          # 日常模式（自由探索）配置
├── 事件系统设计-v2.md             # 事件系统设计文档
└── tools/
    └── validate_content.py        # 校验脚本（支持递归扫描子目录）
```

### 文件格式约定

- **NPC 和事件**：每个文件一个配置，YAML 格式，根节点为字典（mapping）
- **物品**：每个文件一个物品列表，YAML 格式，根节点为列表（list）
- **文件命名**：NPC 使用英文 ID 命名（如 `master.yaml`），事件使用数字前缀 + 英文 ID（如 `01_entrance_trial.yaml`）

---

## 当前交付状态

### 已完成（Day 1-2 目标）

| 产物 | 状态 | 位置 |
|------|------|------|
| content/ 目录结构 | ✅ | `content/` |
| 世界观核心设定初稿 | ✅ | `九洲修仙世界观设定.md` |
| JSON Schema v0.3（支持 major/minor/daily + world_book） | ✅ | `content/schema/` |
| 3 个 NPC 角色卡初稿 | ❌ 已删除（青云门已移除） | `content/npcs/` |
| 5 个大事件配置初稿 | ❌ 已删除，待重新设计 | `content/events/major/` |
| 3 个小事件配置初稿 | ❌ 已删除，待重新设计 | `content/events/minor/` |
| 世界书知识库（11本） | ✅ | `content/world_books/` |
| 世界书 Schema | ✅ | `content/schema/world_book.schema.json` |
| 自由探索配置 | ✅ | `content/free_exploration.yaml` |
| 物品配置初稿 | ✅ | `content/items/` |
| validate_content.py | ✅ | `content/tools/` |
| 事件系统设计文档（世界书增强版） | ✅ | `content/事件系统设计-v2.md` |

### 待完成

| 产物 | 截止 | 位置 |
|------|------|------|
| 优化 NPC 角色卡（补全 relationships 和 dialogue_examples） | Day 4 | `content/npcs/` |
| 完善大事件 agent_guidance | Day 4 | `content/events/major/` |
| 扩展小事件（增至 5-8 个） | Day 4 | `content/events/minor/` |
| 全部配置通过校验（0 error） | Day 4 | - |
| 最终校验所有内容配置 | Day 5 | - |
| 编写测试指南 | Day 5 | `docs/testing-guide.md` |
| 完整事件配置（5 大事件 + 5-8 小事件） | Day 8-10 | `content/events/` |
| 完整 NPC 配置（3 个定稿） | Day 8-10 | `content/npcs/` |
| 内容编辑器（可选 P2） | Day 8-10 | `content/tools/editor.html` |
| 游戏内文案 | Day 12-13 | - |

---

## 内容创作规范

### 新增 NPC 角色卡

1. 在 `content/npcs/` 下创建 `{npc_id}.yaml`
2. 参考 `content/schema/npc.schema.json` 的必填字段
3. 每个 NPC 至少包含 6 个 `dialogue_examples`，覆盖不同好感度层次
4. `knowledge` 字段用于 Agent 叙事注入，写该 NPC 知道的客观事实
5. 创建后运行 `python content/tools/validate_content.py --path content --verbose`

### 新增大事件（major）

大事件是主线剧情，框架固定，玩家选择决定结果。

1. 在 `content/events/major/` 下创建 `{序号}_{event_id}.yaml`
2. 使用 `{序号}` 前缀控制事件顺序（01, 02, 03...）
3. `type: "major"`，必填
4. 每个 scene 必须包含 `agent_guidance`（setting_details、sensory_details、npc_behavior_hints）
5. `next_scene` 可以跨事件跳转（会触发 warning，属正常行为）
6. 关键节点设置 `free_input_enabled: true`，让玩家发挥

### 新增小事件（minor）

小事件是随机触发的自由互动，Agent 全权驱动叙事。

1. 在 `content/events/minor/` 下创建 `{event_id}.yaml`
2. `type: "minor"`，必填
3. 必须配置：`trigger_conditions`、`difficulty`、`free_narrative_hints`
4. 只需要一个入口 scene，开放 `free_input_enabled: true`
5. `free_narrative_hints` 告诉 Agent 背景、主角、NPC、核心冲突——AI 负责后续展开
6. Agent 根据玩家行为判断成功/失败，施加奖励

### 事件通用规则

- 每个 scene 必须包含 `agent_guidance`（setting_details、sensory_details、npc_behavior_hints）
- `next_scene` 可以跨事件跳转（会触发 warning，属正常行为）
- `free_input_enabled: true` 表示该场景允许玩家自由输入，需配合 `free_input_hints`

### 新增世界书知识碎片

1. 在 `content/world_books/` 下的 JSON 文件中追加条目
2. `keys` 是触发关键词，尽量覆盖玩家可能提到的同义词
3. `content` 要简洁但信息完整，控制在 `max_tokens` 范围内
4. `weight` 越高，优先级越高（重要知识设高权重）
5. `sticky` 用于事件持续效果（如：某事件后产生持续影响）
6. `cooldown` 防止同一知识反复触发
7. `probability < 1` 用于稀有知识（如：飞升真相只在特定条件下低概率触发）

**知识碎片设计原则**：
- **原子性**：每个碎片只讲一件事
- **关键词覆盖**：keys 要覆盖玩家可能使用的各种说法
- **内容简洁**：Agent 不需要读论文，需要快速获取关键信息
- **相互独立**：碎片之间不应有强依赖

### 新增物品

1. 在 `content/items/` 下的 YAML 文件中追加条目
2. 文件根节点为列表，每个物品是一个字典元素
3. 物品类型（type）必须是：`consumable`, `equipment`, `material`, `key_item`, `currency`, `skill_book`
4. 稀有度（rarity）必须是：`common`, `uncommon`, `rare`, `epic`, `legendary`

### 校验命令

```bash
# 完整校验
python content/tools/validate_content.py --path content --verbose

# 快速校验（只看错误）
python content/tools/validate_content.py --path content
```

---

## 世界观规范

> **重要**：世界观以 `content/world_books/` 中的世界书知识库为准，`九洲修仙世界观设定.md` 为完整设定文档。Agent 不得引用任何已被删除或屏蔽的设定（如飞升真相、上古灾变事件等）。

### 核心设定

- **世界**：九洲大陆，灵气为能量基础
- **修炼体系**：炼气 → 筑基 → 金丹 → 元婴 → 化神 → 炼虚 → 合体 → 大乘 → 渡劫 → 飞升（传统修仙）
- **灵根**：金木水火土 + 特殊灵根 + 阴阳混沌。灵根决定修炼速度
- **功法品级**：九品 → 一品，同品级下分天地玄黄；一品之上为道藏
- **宗门**：玩家可自选大洲与宗门（详见世界书 `sect_lore.json`、`jiuzhou_geography.json`）
- **渡劫**：渡劫期修士需渡劫，成功则飞升仙界
- **朝代**：大宁王朝（由大秦仙朝延续/更名而来）

### 当前游戏范围

- **MVP 阶段仅开放中洲**，其他大洲作为世界观背景保留，暂不开放
- **核心体验流程**：选择大洲（当前仅中洲）→ 启灵测资质 → 自选宗门 → 入门试炼 → 宗门生活
- 当前阶段聚焦炼气期，暂不涉及高阶境界
- **宗门选择**：中洲提供 4 个可选宗门，涵盖不同修炼方向。青云门、风云殿、竹酒书院已移除（不含）
- 玄清宗、神武门、扶龙宫、红尘阁为可选宗门，玩家可根据资质与喜好自由选择
- **新 NPC 体系待补充**——当前无已配置的 NPC 角色卡

---

## 协作接口

### 人员 B（后端 + Agent 架构）

需要从内容配置中读取：
- `npc.schema.json` → NPC 数据结构
- `event.schema.json` → 事件引擎数据结构
- `agent_guidance` → Prompt 模板素材（setting_details、sensory_details、npc_behavior_hints）
- `dialogue_examples` → Few-shot 示例
- `world_book.schema.json` → 世界书数据结构
- `world_books/*.json` → 知识碎片（Entry）数据
- 世界书扫描模块 → 每次构建 Prompt 前扫描关键词并注入相关知识

### 人员 A（前端）

需要从内容配置中读取：
- 物品名称和描述 → UI 展示
- 境界名称和数值 → 属性面板

### 内容变更流程

1. 修改 `content/` 下的 YAML 文件
2. 运行 `validate_content.py` 确保无错误
3. 如果涉及 Schema 变更，通知人员 B 同步更新引擎
4. Git 提交时使用 Conventional Commits 格式：`feat(content): 新增XXX事件`

---

## 参考资料

- 世界观完整设定：`九洲修仙世界观设定.md`
- 原始设定（仅供参考，勿修改）：`c:\Users\32523\OneDrive\小说世界观\修仙技术设定.md`
- 角色分工：`修仙模拟器-角色分工文档.md`
- 开发计划：`修仙模拟器-三周开发计划与分工-v2.md`