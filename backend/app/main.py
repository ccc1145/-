# ==================== 路径设置（放在所有 import 之前）====================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_SRC = PROJECT_ROOT / "agent" / "src"
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"

sys.path.insert(0, str(AGENT_SRC))
sys.path.insert(0, str(FRAMEWORK_SRC))

# ==================== 标准库与第三方库导入 ====================
import datetime
import os
import random
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# ==================== 本地模块导入 ====================
from app.schemas.game_state import (
    GameState, PlayerState, WorldState, WorldTime, NPCState,
    SpiritRoot, Choice, NarrativeSegment,
    StartSessionRequest, StartSessionResponse,
    ActionRequest, ActionResponse,
    SaveRequest, LoadRequest, SaveResponse,
)
from app.engine import EngineError, GameEngine
from app.services.agent_bridge import AgentBridge

# ==================== 加载环境变量 ====================
load_dotenv()   # 读取 backend/.env

# ==================== FastAPI 应用初始化 ====================
app = FastAPI(title="修仙模拟器后端")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

# ==================== 内存存储 ====================
sessions: dict[str, GameState] = {}
archives: dict[str, dict[str, GameState]] = {}
save_info: dict[str, list[SaveResponse]] = {}

game_engine = GameEngine.default()
agent_bridge = AgentBridge()

# ==================== API 路由 ====================

@app.post("/api/session/start", response_model=StartSessionResponse)
def start_session(request: StartSessionRequest):
    """开始新游戏"""
    session_id = str(uuid4())
    root_type = request.spirit_root_type or random.choice(["金", "木", "水", "火", "土", "杂灵根"])
    quality = random.randint(1, 10)

    state = GameState(
        session_id=session_id,
        current_scene_id="start",
        turn_count=0,
        player=PlayerState(
            name=request.player_name,
            spirit_root=SpiritRoot(type=root_type, quality=quality),
        ),
        npcs={
            "master": NPCState(
                id="master",
                name="玄清真人",
                affinity=0,
                location="试炼场",
            )
        },
        world=WorldState(
            current_location="试炼场",
            time=WorldTime(day=1, period="上午"),
            flags={},
        ),
    )
    sessions[session_id] = state

    opening_narrative = (
        "你站在青云山门前，薄雾如纱，石阶蜿蜒而上。"
        "守门师兄抬眼看了看你，沉声道：‘新来的？进去吧，试炼马上就要开始了。’"
    )
    choices = game_engine.available_choices(state)

    return {
        "session_id": session_id,
        "initial_state": state,
        "opening_narrative": opening_narrative,
        "narrative_segments": [{"type": "narration", "text": opening_narrative}],
        "available_choices": choices,
        "free_input_enabled": True,
    }


@app.post("/api/session/{session_id}/action", response_model=ActionResponse)
def perform_action(session_id: str, request: ActionRequest):
    """处理玩家动作"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        engine_result = game_engine.process_action(
            state, request.action_type, request.payload
        )
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    narrative_result = agent_bridge.generate(engine_result, request.action_type, request.payload)
    sessions[session_id] = engine_result.state

    return {
        "success": True,
        "new_state": engine_result.state,
        "narrative": narrative_result["narrative"],
        "narrative_segments": narrative_result.get("narrative_segments", []),
        "available_choices": engine_result.available_choices,
        "scene_changed": engine_result.scene_changed,
        "scene_id": engine_result.state.current_scene_id,
        "game_over": getattr(engine_result, "game_over", False),
        "free_input_enabled": True,
        "agent_thought": narrative_result.get("thought", None),
        "degraded": narrative_result.get("degraded", False),
    }


@app.get("/api/session/{session_id}/state")
def get_state(session_id: str):
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"state": state}


@app.post("/api/session/{session_id}/save", response_model=SaveResponse)
def save_game(session_id: str, request: SaveRequest):
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    save_id = str(uuid4())
    if session_id not in archives:
        archives[session_id] = {}
        save_info[session_id] = []

    archives[session_id][save_id] = state.copy(deep=True)
    info = SaveResponse(
        save_id=save_id,
        label=request.label,
        saved_at=datetime.datetime.now().isoformat(),
    )
    save_info[session_id].append(info)
    return info


@app.get("/api/session/{session_id}/saves")
def get_saves(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"saves": save_info.get(session_id, [])}


@app.post("/api/session/{session_id}/load")
def load_game(session_id: str, request: LoadRequest):
    if session_id not in archives or request.save_id not in archives.get(session_id, {}):
        raise HTTPException(status_code=404, detail="存档不存在")
    state = archives[session_id][request.save_id].copy(deep=True)
    sessions[session_id] = state
    return {"state": state}