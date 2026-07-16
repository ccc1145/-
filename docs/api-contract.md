# API 契约 v1.0

Base URL: `http://localhost:8000`

## 1. 开始新游戏
**POST** `/session/start`

Request: 无需 body（暂时），以后可传入玩家姓名。
Response:
{
  "session_id": "sess_abc123",
  "game_state": { /* GameState 对象 */ }
}

## 2. 获取游戏状态
**GET** `/session/{session_id}`

Response: `{ "game_state": { ... } }`

## 3. 玩家行动
**POST** `/session/{session_id}/action?choice_id=climb_stairs`

Request: query parameter `choice_id`（后续改为 JSON body）。

Response:
{
  "game_state": { /* 更新后的 GameState */ },
  "narrative": "...",
  "available_choices": [...]
}

错误响应：`{"error": "会话不存在"}`