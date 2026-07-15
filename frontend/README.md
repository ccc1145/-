# 修仙模拟器前端（角色 A）

## 已包含

- React + TypeScript + Vite + Tailwind CSS 4
- Zustand 游戏状态管理
- Axios API Client
- 可切换 Mock / 真实后端
- 开始游戏界面
- 剧情打字机效果
- 预设选择
- 自由输入
- 玩家状态、NPC 好感度、储物袋
- GameState 调试面板
- 一条可独立跑通的 Mock MVP 主线

## 运行

```bash
npm install
npm run dev
```

默认使用 Mock 模式，不依赖后端。

## 接入真实后端

复制 `.env.example` 为 `.env`，修改：

```env
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000/api
```

然后重启 `npm run dev`。
