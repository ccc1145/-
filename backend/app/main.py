import copy
import datetime
import random
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# 导入所有新定义的 Pydantic 模型
from app.schemas.game_state import (
    GameState, PlayerState, WorldState, WorldTime,
    NPCState, SpiritRoot, Choice, NarrativeSegment,
    StartSessionRequest, StartSessionResponse,
    ActionRequest, ActionResponse,
    SaveRequest, LoadRequest, SaveResponse,
)

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
archives: dict[str, dict[str, GameState]] = {}  # archives[session_id][save_id] = GameState
save_info: dict[str, list[SaveResponse]] = {}   # 每个会话的存档列表


# ============ API 路由（所有路径均以 /api 开头） ============

@app.post("/api/session/start", response_model=StartSessionResponse)
def start_session(request: StartSessionRequest):
    """开始新游戏"""
    session_id = str(uuid4())

    # 处理灵根：未提供则随机
    root_type = request.spirit_root_type or random.choice(["金", "木", "水", "火", "土", "杂灵根"])
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
    choices = [
        Choice(id="enter_trial", text="踏入试炼场"),
        Choice(id="look_around", text="环顾四周，观察环境"),
    ]

    return {
        "session_id": session_id,
        "initial_state": state,
        "opening_narrative": opening_narrative,
        "narrative_segments": [
            {"type": "narration", "text": opening_narrative}
        ],
        "available_choices": choices,
        "free_input_enabled": True,
    }


@app.post("/api/session/{session_id}/action", response_model=ActionResponse)
def perform_action(session_id: str, request: ActionRequest):
    """处理玩家动作（选择或自由输入）"""
    state = sessions.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    state.turn_count += 1
    narrative = ""
    choices = []
    scene_id = state.current_scene_id

    # ---- 临时硬编码逻辑（后续将替换为 Agent 调用） ----
    if request.action_type == "choice":
        payload = request.payload
        if payload == "enter_trial":
            narrative = (
                "你深吸一口气，踏入试炼场。中央立着一块三尺高的测灵石，"
                "散发着淡淡的青光。玄清真人站在一旁，目光如炬。"
            )
            choices = [
                Choice(id="touch_stone", text="将手放在测灵石上"),
                Choice(id="hesitate", text="犹豫不决，暗自观察其他弟子"),
            ]
            state.player.cultivation += 5
            state.world.flags["entered_trial"] = True
            scene_id = "trial_grounds"

        elif payload == "look_around":
            narrative = (
                "你环顾四周，发现路边有一株奇异的灵芝，似乎有微弱的灵力波动。"
                "不远处还有几个和你一样的新弟子在交头接耳。"
            )
            choices = [
                Choice(id="pick_herb", text="采摘灵芝"),
                Choice(id="talk_to_others", text="走过去与弟子们攀谈"),
            ]

        elif payload == "touch_stone":
            root = state.player.spirit_root
            narrative = (
                f"你将手放在测灵石上，一股温和的气息顺着手臂流入体内。"
                f"测灵石逐渐亮起{root.type}色的光芒，光芒越来越盛。"
                f"玄清真人微微颔首：‘嗯，{root.type}灵根，品质{root.quality}等。尚可。’"
            )
            choices = [
                Choice(id="express_gratitude", text="弟子拜谢长老"),
                Choice(id="stay_silent", text="默默退到一旁"),
            ]
            state.player.cultivation += 10
            state.player.realm.minor += 1   # 修炼小层提升
            state.npcs["master"].affinity += 3

        else:
            narrative = "你有些迷茫，站在原地没有动弹。"
            choices = [
                Choice(id="enter_trial", text="前往试炼场"),
                Choice(id="look_around", text="观察周围"),
            ]

    elif request.action_type == "free_input":
        # 自由输入占位处理：直接回显
        narrative = f"你说“{request.payload}”，但在嘈杂的环境中，暂时没有人注意到你。"
        choices = [
            Choice(id="enter_trial", text="前往试炼场"),
            Choice(id="look_around", text="继续观察周围"),
        ]
    else:
        narrative = "无效的操作，时间仿佛停滞了一瞬。"
        choices = []

    # 更新场景 ID
    state.current_scene_id = scene_id
    # 写回存储（内存中本来就是引用，但显式写一下）
    sessions[session_id] = state

    return {
        "success": True,
        "new_state": state,
        "narrative": narrative,
        "narrative_segments": [{"type": "narration", "text": narrative}],
        "available_choices": choices,
        "scene_changed": scene_id != state.current_scene_id,
        "scene_id": scene_id,
        "game_over": False,
        "free_input_enabled": True,
        "agent_thought": None,
        "degraded": False,
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
    """获取该会话的所有存档列表"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"saves": save_info.get(session_id, [])}


@app.post("/api/session/{session_id}/load")
def load_game(session_id: str, request: LoadRequest):
    """读取存档"""
    if session_id not in archives or request.save_id not in archives.get(session_id, {}):
        raise HTTPException(status_code=404, detail="存档不存在")

    # 恢复状态
    state = archives[session_id][request.save_id].copy(deep=True)
    sessions[session_id] = state
    return {"state": state}