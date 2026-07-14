
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from backend.app.config import engine, Base, SessionLocal
from backend.app.models.game_state import GameSave  
from backend.app.schemas.game_state import GameState
import datetime

app = FastAPI(title="修仙模拟器后端")

# 启动时自动建表
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# 获取数据库会话的依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/session/start")
def start_session(db: Session = Depends(get_db)):
    # 创建一个新的游戏状态
    state = GameState()
    # 保存到数据库
    db_save = GameSave(
        session_id="demo_session_1",
        game_state=state.dict(),
        created_at=datetime.datetime.now().isoformat()
    )
    db.add(db_save)
    db.commit()
    db.refresh(db_save)
    return {
        "session_id": db_save.session_id,
        "game_state": state.dict(),
        "message": "新游戏已创建"
    }

@app.get("/session/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    save = db.query(GameSave).filter(GameSave.session_id == session_id).first()
    if not save:
        return {"error": "存档不存在"}
    return {"session_id": save.session_id, "game_state": save.game_state}