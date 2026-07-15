from sqlalchemy import Column, Integer, String, JSON
from backend.app.config import Base

class GameSave(Base):
    __tablename__ = "game_saves"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    game_state = Column(JSON) 
    created_at = Column(String)