# 修仙模拟器

AI 驱动的文字冒险修仙游戏。项目由 React 前端、FastAPI 后端和 LLM Agent 叙事引擎组成。

## 一键启动（Windows）

首次运行前，请确保电脑已安装：

- Python 3.11 或更高版本
- Node.js 20 或更高版本（包含 npm）

然后双击项目根目录下的 `start.bat`。

启动脚本会自动：

1. 检查 Python、Node.js 和 npm。
2. 在 `backend/.venv` 创建独立的 Python 虚拟环境。
3. 安装缺失的前后端依赖。
4. 创建缺失的本地环境配置。
5. 分别启动后端和前端服务。
6. 在服务就绪后打开浏览器。

服务地址：

- 游戏前端：<http://localhost:5173>
- 后端 API：<http://localhost:8000/api>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

关闭启动后出现的前端、后端服务窗口即可停止项目。

## 配置大模型 API

项目可通过 DeepSeek 兼容接口生成 AI 叙事。编辑 `backend/.env`：

```env
LLM_PROVIDER=openai
LLM_MODEL=deepseek-v4-flash
LLM_MAX_TOKENS=1024
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=2
LLM_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=你的真实API_KEY
DATABASE_URL=sqlite:///./xiuzhen.db
```

可以在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建 API Key。

> 请勿把 API Key 写入 `.env.example` 或提交到 Git。项目已通过 `.gitignore` 忽略本地 `.env` 文件。

修改配置后，需要关闭服务窗口并重新运行 `start.bat`。

## 没有 API Key 时运行

没有 API Key 时，后端仍可启动，并可能使用本地降级叙事。若要完全绕过后端并使用前端内置数据，可编辑 `frontend/.env`：

```env
VITE_USE_MOCK=true
VITE_API_BASE_URL=http://localhost:8000/api
```

保存后重新启动项目。需要连接真实后端时，将 `VITE_USE_MOCK` 改回 `false`。

## 手动启动

### 后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

在另一个终端中运行：

```powershell
cd frontend
npm install
npm run dev
```

如果 PowerShell 阻止运行 `npm.ps1`，可以改用：

```powershell
npm.cmd run dev
```

## 常见问题

### 提示找不到 Python 或 Node.js

安装对应运行环境后，重新打开终端或重启电脑，确保 `python`、`node` 和 `npm` 已加入系统 `PATH`。

### 前端打开后无法连接后端

检查以下项目：

- 后端窗口是否仍在运行。
- <http://localhost:8000/api/health> 是否可以访问。
- `frontend/.env` 中的 `VITE_API_BASE_URL` 是否为 `http://localhost:8000/api`。
- 端口 `8000` 是否被其他程序占用。

### AI 叙事不可用

检查 `backend/.env` 中的 API Key、模型名称、接口地址以及账户余额。不要在错误截图或日志中公开完整 API Key。

### 端口被占用

关闭占用 `5173` 或 `8000` 端口的程序，再重新运行 `start.bat`。

## 项目结构

```text
agent/                 LLM Agent 叙事模块
ai_agent_framework/    AI Agent 基础框架
backend/               FastAPI 后端
content/               NPC、事件、物品和世界书配置
docs/                  接口与开发文档
frontend/              React + TypeScript 前端
tools/                 项目辅助工具
start.bat              Windows 一键启动入口
```

内容配置的具体规范请参阅 `AGENTS.md` 和 `content/事件系统设计-v2.md`。

