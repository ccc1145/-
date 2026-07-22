from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal

# ---------- 基础类型 ----------
SpiritRootType = Literal["金", "木", "水", "火", "土", "杂灵根"]
RealmMajor = Literal["练气", "筑基"]
TimePeriod = Literal["早晨", "上午", "下午", "傍晚", "夜晚"]
NarrativeSegmentType = Literal["narration", "dialogue"]
ActionType = Literal["choice", "free_input"]


class ItemEffect(BaseModel):
    type: str
    value: Optional[int] = None
    description: Optional[str] = None


class InventoryItem(BaseModel):
    item_id: str
    name: str
    quantity: int
    effects: List[ItemEffect] = []


class PlayerAttributes(BaseModel):
    strength: int = 5
    agility: int = 5
    intelligence: int = 5
    perception: int = 5


class SpiritRoot(BaseModel):
    type: SpiritRootType = "杂灵根"
    quality: int = 1


class Realm(BaseModel):
    major: RealmMajor = "练气"
    minor: int = 1


class PlayerState(BaseModel):
    name: str = "无名修士"
    cultivation: int = 0
    realm: Realm = Realm()
    spirit_root: SpiritRoot = SpiritRoot()
    attributes: PlayerAttributes = PlayerAttributes()
    inventory: List[InventoryItem] = []
    hp: Optional[int] = 100
    max_hp: Optional[int] = 100
    mp: Optional[int] = 50
    max_mp: Optional[int] = 50
    spirit_stones: int = 0
    skills: List[str] = []


class NPCState(BaseModel):
    id: str
    name: str
    affinity: int = 0
    location: str = ""
    known_info: List[str] = []
    dialogue_history: List[str] = []


class WorldTime(BaseModel):
    day: int = 1
    period: TimePeriod = "上午"


class WorldState(BaseModel):
    current_location: str = "青云门山门"
    time: WorldTime = WorldTime()
    flags: Dict[str, bool] = {}


class EventRecord(BaseModel):
    turn: int
    scene_id: str
    narrative: str
    player_choice: str
    state_changes: Dict[str, Any] = {}
    timestamp: str = ""


class FreeInputRecord(BaseModel):
    turn: int
    input_text: str
    interpreted_intent: str
    narrative_response: str
    timestamp: str = ""


class GameState(BaseModel):
    session_id: str = ""
    current_scene_id: str = "start"
    turn_count: int = 0
    player: PlayerState = PlayerState()
    npcs: Dict[str, NPCState] = {}
    world: WorldState = WorldState()
    narrative: str = ""                              # 当前场景叙事
    available_choices: List[Dict[str, Any]] = []     # 当前可用选项
    recent_events: List[EventRecord] = []            # 最近事件
    free_input_history: List[FreeInputRecord] = []   # 自由输入历史


# ---------- 前端交互模型 ----------
class Choice(BaseModel):
    id: str
    text: str
    disabled: Optional[bool] = False


class NarrativeSegment(BaseModel):
    type: NarrativeSegmentType
    text: str
    speaker: Optional[str] = None


class StartSessionRequest(BaseModel):
    player_name: str = "无名修士"
    spirit_root_type: Optional[SpiritRootType] = None


class ActionRequest(BaseModel):
    action_type: ActionType
    payload: str


class StartSessionResponse(BaseModel):
    session_id: str
    initial_state: GameState
    opening_narrative: str
    narrative_segments: List[NarrativeSegment] = []
    available_choices: List[Choice] = []
    free_input_enabled: bool = True


class ActionResponse(BaseModel):
    success: bool = True
    new_state: GameState
    narrative: str
    narrative_segments: List[NarrativeSegment] = []
    available_choices: List[Choice] = []
    scene_changed: bool = False
    scene_id: str = ""
    game_over: bool = False
    free_input_enabled: bool = True
    agent_thought: Optional[str] = None
    degraded: bool = False


class SaveRequest(BaseModel):
    label: str


class LoadRequest(BaseModel):
    save_id: str


class SaveResponse(BaseModel):
    save_id: str
    label: str
    saved_at: str