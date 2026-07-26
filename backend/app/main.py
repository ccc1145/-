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
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import engine, Base, SessionLocal
from app.models.game_state import GameSave, User
from app.schemas.game_state import (
    GameState, PlayerState, WorldState, WorldTime, NPCState, EventRecord, FreeInputRecord,
    SpiritRoot, Choice, NarrativeSegment,
    StartSessionRequest, StartSessionResponse,
    ActionRequest, ActionResponse,
    SaveRequest, LoadRequest, SaveResponse, AuthRequest, AuthResponse,
)
from app.engine import EngineError, GameEngine
from app.services.agent_bridge import AgentBridge
from app.services.auth import create_token, decode_token, hash_password, verify_password

# ==================== 加载环境变量 ====================
load_dotenv(PROJECT_ROOT / "backend" / ".env")

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

# Lightweight SQLite migration for installations created before user accounts.
with engine.begin() as connection:
    columns = {column["name"] for column in inspect(engine).get_columns("game_saves")}
    if "user_id" not in columns:
        connection.execute(text("ALTER TABLE game_saves ADD COLUMN user_id INTEGER"))
    if "player_name" not in columns:
        connection.execute(text("ALTER TABLE game_saves ADD COLUMN player_name VARCHAR(50) DEFAULT ''"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- 内存会话（运行时状态，重启后丢失但可从存档恢复） ----------
sessions: dict[str, GameState] = {}
session_users: dict[str, int] = {}


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    payload = decode_token(authorization[7:])
    user = db.get(User, payload.get("sub")) if payload else None
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return user


def require_session_owner(session_id: str, user: User) -> None:
    if session_users.get(session_id) != user.id:
        raise HTTPException(status_code=404, detail="游戏会话不存在")


@app.post("/api/auth/register", response_model=AuthResponse)
def register(request: AuthRequest, db: Session = Depends(get_db)):
    username = request.username.strip()
    if not 3 <= len(username) <= 32:
        raise HTTPException(status_code=400, detail="用户名长度需要为 3-32 个字符")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要 6 个字符")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(username=username, password_hash=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(token=create_token(user.id, user.username), username=user.username)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username.strip()).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return AuthResponse(token=create_token(user.id, user.username), username=user.username)


@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {"username": user.username}

# 初始化引擎与 Agent 桥接
game_engine = GameEngine.from_formal_content(PROJECT_ROOT / "content")
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
def start_session(request: StartSessionRequest, user: User = Depends(get_current_user)):
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
        npcs={},
        world=WorldState(
            current_location="中洲启灵台",
            time=WorldTime(day=1, period="上午"),
            flags={"game_start": True},
        ),
    )
    sessions[session_id] = state
    session_users[session_id] = user.id

    opening_narrative = game_engine.scene("start").description
    choices = game_engine.available_choices(state)

    # 持久化叙事和选项到 GameState 中（便于存档）
    state.narrative = opening_narrative
    state.available_choices = [c.dict() for c in choices]
    state.recent_events.append(
        EventRecord(
            turn=0,
            scene_id="start",
            narrative=opening_narrative,
            player_choice="踏入仙途",
            state_changes={},
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
    )

    return {
        "session_id": session_id,
        "initial_state": state,
        "opening_narrative": opening_narrative,
        "narrative_segments": [{"type": "narration", "text": opening_narrative}],
        "available_choices": choices,
        "free_input_enabled": True,
    }


@app.post("/api/session/{session_id}/action", response_model=ActionResponse)
def perform_action(session_id: str, request: ActionRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """处理玩家动作（选择或自由输入）"""
    require_session_owner(session_id, user)
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    # Lazily add an explicitly mentioned authored NPC to authoritative state.
    if request.action_type == "free_input":
        for npc_id, card in agent_bridge.npc_cards.get_all_npcs().items():
            npc_name = card.get("name", "")
            if npc_name and npc_name in request.payload and npc_id not in state.npcs:
                initial = card.get("initial_state", {})
                state.npcs[npc_id] = NPCState(
                    id=npc_id,
                    name=npc_name,
                    affinity=initial.get("affinity", 0),
                    location=initial.get("location", ""),
                    known_info=card.get("knowledge", []),
                )
                break

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
            state.recent_events.append(
                EventRecord(
                    turn=state.turn_count,
                    scene_id=state.current_scene_id,
                    narrative=narrative,
                    player_choice=request.payload,
                    state_changes={},
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )
            )
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
    if engine_result.scene_changed:
        state.world.current_location = game_engine.scene(state.current_scene_id).name

    # 将叙事和选项写入 state（用于存档）
    state.narrative = narrative_result["narrative"]
    choices = engine_result.available_choices
    state.available_choices = [c.dict() if hasattr(c, 'dict') else c for c in choices]
    raw_changes = engine_result.event_context.get("authoritative_state_changes", [])
    state.recent_events.append(
        EventRecord(
            turn=state.turn_count,
            scene_id=state.current_scene_id,
            narrative=narrative_result["narrative"],
            player_choice=request.payload,
            state_changes={
                change.get("target", f"change_{index}"): change.get("after")
                for index, change in enumerate(raw_changes)
            },
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
    )

    if request.action_type == "free_input":
        state.free_input_history.append(
            FreeInputRecord(
                turn=state.turn_count,
                input_text=request.payload,
                interpreted_intent=(narrative_result.get("intent") or {}).get("intent", "unknown"),
                narrative_response=narrative_result["narrative"],
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        )

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
def get_state(session_id: str, user: User = Depends(get_current_user)):
    """获取当前游戏状态"""
    require_session_owner(session_id, user)
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"state": state}


# ==================== 存档路由 ====================

@app.post("/api/session/{session_id}/save", response_model=SaveResponse)
def save_game(session_id: str, request: SaveRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """手动存档"""
    require_session_owner(session_id, user)
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")
    save_id = str(uuid4())
    save_record = GameSave(
        session_id=session_id,
        user_id=user.id,
        player_name=state.player.name,
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
        saved_at=save_record.created_at.isoformat() if save_record.created_at else "",
        player_name=state.player.name,
        turn_count=state.turn_count,
    )


@app.get("/api/session/{session_id}/saves")
def get_saves(session_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取当前账号的全部角色存档。"""
    require_session_owner(session_id, user)
    records = (
        db.query(GameSave)
        .filter(GameSave.user_id == user.id)
        .order_by(GameSave.created_at.desc())
        .all()
    )
    result = [
        SaveResponse(
            save_id=r.save_id,
            label=r.label,
            saved_at=r.created_at.isoformat() if r.created_at else "",
            player_name=r.player_name or GameState.model_validate_json(r.game_state).player.name,
            turn_count=GameState.model_validate_json(r.game_state).turn_count,
        ) for r in records
    ]
    return {"saves": result}


@app.delete("/api/session/{session_id}/saves/{save_id}")
def delete_save(session_id: str, save_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """删除指定存档"""
    require_session_owner(session_id, user)
    record = (
        db.query(GameSave)
        .filter(GameSave.save_id == save_id, GameSave.user_id == user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="存档不存在")
    db.delete(record)
    db.commit()
    return {"message": "存档已删除"}


@app.post("/api/session/{session_id}/load")
def load_game(session_id: str, request: LoadRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """加载存档"""
    require_session_owner(session_id, user)
    record = (
        db.query(GameSave)
        .filter(GameSave.save_id == request.save_id, GameSave.user_id == user.id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="存档不存在")

    state = GameState.model_validate_json(record.game_state)
    # A save can come from any character session owned by this account.
    state.session_id = session_id
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
