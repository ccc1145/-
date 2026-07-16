# 游戏引擎核心

## 一分钟说明

- `GameState`：当前游戏的唯一真实状态。
- 事件：策划预先定义的剧情节点。
- 触发条件：决定某个选项当前是否可用。
- 效果：经过白名单校验后对 GameState 进行的确定性修改。
- Agent：只根据引擎提供的上下文生成叙事，不直接修改 GameState。

## 调用边界

```python
result = GameEngine.process_action(state, action_type, payload)
```

该方法不会修改传入的 `state`，而是返回包含新状态、事件上下文、下一组选项和场景变化信息的 `EngineResult`。非法动作或非法配置会在写入 Session 前失败。

正式内容发布前，`GameEngine.default()` 使用内置的入门试炼配置。内容分支提交后，后端可通过 `GameEngine.from_event_directory("content/events")` 加载 YAML；字段与开发计划中的事件配置示例兼容。

## 权威状态规则

FastAPI 将 `EngineResult.event_context` 交给 Agent 桥接层。桥接层只解析叙事、叙事分段和调试说明；即使模型返回 `state_changes`，该字段也会被忽略。所有修为、境界、Flag 和 NPC 好感度变化必须由引擎配置触发。
