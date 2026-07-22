# ==================== 路径设置 ====================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_SRC = PROJECT_ROOT / "agent" / "src"
FRAMEWORK_SRC = PROJECT_ROOT / "ai_agent_framework" / "src"

sys.path.insert(0, str(AGENT_SRC))
sys.path.insert(0, str(FRAMEWORK_SRC))

# ==================== 标准库与第三方导入 ====================
import datetime
import os
import random
import traceback
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import engine, Base, SessionLocal
from app.models.game_state import GameSave
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
load_dotenv()

# ==================== FastAPI 应用 ====================
app = FastAPI(title="修仙模拟器后端")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],      # 前端开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 全局异常处理（返回 JSON 而非 HTML） ----------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()  # 控制台输出详细错误，方便调试
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc)},
    )

# ---------- HTTPException 自定义格式 ----------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

# ---------- 数据库初始化 ----------
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- 内存会话（运行时状态，重启后丢失但可从存档恢复） ----------
sessions: dict[str, GameState] = {}

# 初始化引擎与 Agent 桥接
game_engine = GameEngine.default()
agent_bridge = AgentBridge()

# ==================== 健康检查 ====================
@app.get("/api/health")
def health_check():
    agent_ok = True
    try:
        agent_ok = not agent_bridge.llm_adapter.is_fake if hasattr(agent_bridge.llm_adapter, 'is_fake') else True
    except Exception:
        agent_ok = False
    return {"status": "ok", "agent_available": agent_ok}

# ==================== 游戏路由 ====================

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

    # 持久化叙事和选项到 GameState 中（便于存档）
    state.narrative = opening_narrative
    state.available_choices = [c.dict() for c in choices]

    return {
        "session_id": session_id,
        "initial_state": state,
        "opening_narrative": opening_narrative,
        "narrative_segments": [{"type": "narration", "text": opening_narrative}],
        "available_choices": choices,
        "free_input_enabled": True,
    }


@app.post("/api/session/{session_id}/action", response_model=ActionResponse)
def perform_action(session_id: str, request: ActionRequest, db: Session = Depends(get_db)):
    """处理玩家动作（选择或自由输入）"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    # ---------- 1. 尝试引擎处理 ----------
    try:
        engine_result = game_engine.process_action(
            state, request.action_type, request.payload
        )
    except EngineError as exc:
        # 如果是自由输入且引擎不支持，则降级为通用叙事，不改变状态
        if request.action_type == "free_input":
            narrative = f"你自言自语：“{request.payload}”，但似乎没有引起任何变化。"
            choices = game_engine.available_choices(state)
            # 直接返回，不修改游戏状态
            return {
                "success": True,
                "new_state": state,
                "narrative": narrative,
                "narrative_segments": [{"type": "narration", "text": narrative}],
                "available_choices": choices,
                "scene_changed": False,
                "scene_id": state.current_scene_id,
                "game_over": False,
                "free_input_enabled": True,
                "agent_thought": None,
                "degraded": True,
            }
        else:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ---------- 2. Agent 叙事 ----------
    narrative_result = agent_bridge.generate(engine_result, request.action_type, request.payload)

    # ---------- 3. 更新内存状态 ----------
    sessions[session_id] = engine_result.state
    state = engine_result.state

    # 将叙事和选项写入 state（用于存档）
    state.narrative = narrative_result["narrative"]
    choices = engine_result.available_choices
    state.available_choices = [c.dict() if hasattr(c, 'dict') else c for c in choices]

    try:
        auto_save = GameSave(
            session_id=session_id,
            save_id=str(uuid4()),
            label="自动存档",
            game_state=state.json(),
        )
        db.add(auto_save)
        db.commit()
    except Exception as e:
        print(f"自动存档失败: {e}")

    return {
        "success": True,
        "new_state": state,
        "narrative": narrative_result["narrative"],
        "narrative_segments": narrative_result.get("narrative_segments", []),
        "available_choices": choices,
        "scene_changed": engine_result.scene_changed,
        "scene_id": state.current_scene_id,
        "game_over": getattr(engine_result, "game_over", False),
        "free_input_enabled": True,
        "agent_thought": narrative_result.get("thought", None),
        "degraded": narrative_result.get("degraded", False),
    }


@app.get("/api/session/{session_id}/state")
def get_state(session_id: str):
    """获取当前游戏状态"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"state": state}


# ==================== 存档路由 ====================

@app.post("/api/session/{session_id}/save", response_model=SaveResponse)
def save_game(session_id: str, request: SaveRequest, db: Session = Depends(get_db)):
    """手动存档"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    save_id = str(uuid4())
    save_record = GameSave(
        session_id=session_id,
        save_id=save_id,
        label=request.label,
        game_state=state.json(),
    )
    db.add(save_record)
    db.commit()
    db.refresh(save_record)
    return SaveResponse(
        save_id=save_id,
        label=request.label,
        saved_at=save_record.created_at.isoformat() if save_record.created_at else ""
    )


@app.get("/api/session/{session_id}/saves")
def get_saves(session_id: str, db: Session = Depends(get_db)):
    """获取该会话的存档列表"""
    records = (
        db.query(GameSave)
        .filter(GameSave.session_id == session_id)
        .order_by(GameSave.created_at.desc())
        .all()
    )
    result = [
        SaveResponse(
            save_id=r.save_id,
            label=r.label,
            saved_at=r.created_at.isoformat() if r.created_at else ""
        )
        for r in records
    ]
    return {"saves": result}


@app.delete("/api/session/{session_id}/saves/{save_id}")
def delete_save(session_id: str, save_id: str, db: Session = Depends(get_db)):
    """删除指定存档"""
    record = (
        db.query(GameSave)
        .filter(GameSave.save_id == save_id, GameSave.session_id == session_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="存档不存在")
    db.delete(record)
    db.commit()
    return {"message": "存档已删除"}


@app.post("/api/session/{session_id}/load")
def load_game(session_id: str, request: LoadRequest, db: Session = Depends(get_db)):
    """加载存档"""
    record = (
        db.query(GameSave)
        .filter(GameSave.save_id == request.save_id, GameSave.session_id == session_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="存档不存在")

    state = GameState.parse_raw(record.game_state)
    sessions[session_id] = state   # 恢复到内存中

    # 尝试重新获取该场景的可用选项（若引擎已加载则动态生成，否则使用存档中的选项）
    try:
        choices = game_engine.available_choices(state)
        state.available_choices = [c.dict() if hasattr(c, 'dict') else c for c in choices]
    except Exception:
        choices = state.available_choices if state.available_choices else []

    return {
        "state": state,
        "available_choices": choices,
        "free_input_enabled": True,
        "game_over": False,
    }