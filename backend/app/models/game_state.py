from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.config import Base

class GameSave(Base):
    __tablename__ = "game_saves"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), index=True)   # UUID 长度
    save_id = Column(String(36), unique=True, nullable=False)  # 存档唯一标识
    label = Column(String(100), default="自动存档")
    game_state = Column(Text)                     # 存储 JSON 字符串
    created_at = Column(DateTime, server_default=func.now())   # 自动生成时间戳