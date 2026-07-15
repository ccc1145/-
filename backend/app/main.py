import datetime
import random
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# 导入所有新定义的 Pydantic 模型
from app.schemas.game_state import (
    GameState,
    PlayerState,
    WorldState,
    WorldTime,
    NPCState,
    SpiritRoot,
    StartSessionRequest,
    StartSessionResponse,
    ActionRequest,
    ActionResponse,
    SaveRequest,
    LoadRequest,
    SaveResponse,
)
from app.engine import EngineError, GameEngine
from app.services.agent_bridge import AgentBridge

app = FastAPI(title="修仙模拟器后端")


# ============ 自定义错误处理：返回前端期望的 "error" 字段 ============
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


# ============ 临时内存存储（后续替换为数据库） ============
sessions: dict[str, GameState] = {}
archives: dict[str, dict[str, GameState]] = (
    {}
)  # archives[session_id][save_id] = GameState
save_info: dict[str, list[SaveResponse]] = {}  # 每个会话的存档列表
game_engine = GameEngine.default()
agent_bridge = AgentBridge()


# ============ API 路由（所有路径均以 /api 开头） ============


@app.post("/api/session/start", response_model=StartSessionResponse)
def start_session(request: StartSessionRequest):
    """开始新游戏"""
    session_id = str(uuid4())

    # 处理灵根：未提供则随机
    root_type = request.spirit_root_type or random.choice(
        ["金", "木", "水", "火", "土", "杂灵根"]
    )
    quality = random.randint(1, 10)

    # 构建初始 GameState
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

    # 开场叙事
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
    """处理玩家动作（选择或自由输入）"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        engine_result = game_engine.process_action(
            state, request.action_type, request.payload
        )
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # The engine is the only authority allowed to update GameState. The Agent
    # consumes event_context and may only supply narrative fields.
    narrative_result = agent_bridge.generate(engine_result)
    sessions[session_id] = engine_result.state

    return {
        "success": True,
        "new_state": engine_result.state,
        "narrative": narrative_result.narrative,
        "narrative_segments": narrative_result.narrative_segments,
        "available_choices": engine_result.available_choices,
        "scene_changed": engine_result.scene_changed,
        "scene_id": engine_result.state.current_scene_id,
        "game_over": engine_result.game_over,
        "free_input_enabled": engine_result.free_input_enabled,
        "agent_thought": narrative_result.thought,
        "degraded": narrative_result.degraded,
    }


@app.get("/api/session/{session_id}/state")
def get_state(session_id: str):
    """获取当前游戏状态（前端轮询或刷新用）"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"state": state}


@app.post("/api/session/{session_id}/save", response_model=SaveResponse)
def save_game(session_id: str, request: SaveRequest):
    """保存游戏"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    save_id = str(uuid4())
    if session_id not in archives:
        archives[session_id] = {}
        save_info[session_id] = []

    # 深拷贝当前状态
    archives[session_id][save_id] = state.model_copy(deep=True)

    info = SaveResponse(
        save_id=save_id,
        label=request.label,
        saved_at=datetime.datetime.now().isoformat(),
    )
    save_info[session_id].append(info)
    return info


@app.get("/api/session/{session_id}/saves")
def get_saves(session_id: str):
    """获取该会话的所有存档列表"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"saves": save_info.get(session_id, [])}


@app.post("/api/session/{session_id}/load")
def load_game(session_id: str, request: LoadRequest):
    """读取存档"""
    if session_id not in archives or request.save_id not in archives.get(
        session_id, {}
    ):
        raise HTTPException(status_code=404, detail="存档不存在")

    # 恢复状态
    state = archives[session_id][request.save_id].model_copy(deep=True)
    sessions[session_id] = state
    return {"state": state}
