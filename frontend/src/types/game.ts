export type SpiritRootType = '金' | '木' | '水' | '火' | '土' | '杂灵根'
export type RealmMajor = '练气' | '筑基'
export type TimePeriod = '早晨' | '上午' | '下午' | '傍晚' | '夜晚'
export type NarrativeSegmentType = 'narration' | 'dialogue'
export type ActionType = 'choice' | 'free_input'

export interface ItemEffect {
  type: string
  value: number | null
  description: string | null
}

export interface InventoryItem {
  item_id: string
  name: string
  quantity: number
  effects: ItemEffect[]
}

export interface PlayerAttributes {
  strength: number
  agility: number
  intelligence: number
  perception: number
}

export interface PlayerState {
  name: string
  cultivation: number
  realm: {
    major: RealmMajor
    minor: number
  }
  spirit_root: {
    type: SpiritRootType
    quality: number
  }
  attributes: PlayerAttributes
  inventory: InventoryItem[]
  hp: number | null
  max_hp: number | null
  mp: number | null
  max_mp: number | null
  spirit_stones: number
  skills: string[]
}

export interface NPCState {
  id: string
  name: string
  affinity: number
  location: string
  known_info: string[]
  dialogue_history: string[]
}

export interface EventRecord {
  turn: number
  scene_id: string
  narrative: string
  player_choice: string
  state_changes: Record<string, unknown>
  timestamp: string
}

export interface FreeInputRecord {
  turn: number
  input_text: string
  interpreted_intent: string
  narrative_response: string
  timestamp: string
}

export interface GameState {
  session_id: string
  current_scene_id: string
  turn_count: number
  player: PlayerState
  npcs: Record<string, NPCState>
  world: {
    current_location: string
    time: {
      day: number
      period: TimePeriod
    }
    flags: Record<string, boolean>
  }
  recent_events: EventRecord[]
  free_input_history: FreeInputRecord[]
}

export interface NarrativeSegment {
  type: NarrativeSegmentType
  text: string
  speaker?: string
}

export interface Choice {
  id: string
  text: string
  disabled?: boolean
}

export interface StartSessionRequest {
  player_name: string
  spirit_root_type?: SpiritRootType
}

export interface StartSessionResponse {
  session_id: string
  initial_state: GameState
  opening_narrative: string
  narrative_segments?: NarrativeSegment[]
  available_choices?: Choice[]
  free_input_enabled?: boolean
}

export interface ActionRequest {
  action_type: ActionType
  payload: string
}

export interface ActionResponse {
  success: boolean
  new_state: GameState
  narrative: string
  narrative_segments: NarrativeSegment[]
  available_choices: Choice[]
  scene_changed: boolean
  scene_id: string
  game_over: boolean
  free_input_enabled: boolean
  agent_thought?: string
  degraded?: boolean
}

export interface SaveInfo {
  save_id: string
  label: string
  saved_at: string
}
