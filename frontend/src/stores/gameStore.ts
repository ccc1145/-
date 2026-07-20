import { create } from 'zustand'
import { gameApi } from '../api/client'
import type {
  Choice,
  GameState,
  NarrativeSegment,
  SaveInfo,
  SpiritRootType,
} from '../types/game'

interface GameStore {
  gameState: GameState | null
  narrativeSegments: NarrativeSegment[]
  availableChoices: Choice[]
  freeInputEnabled: boolean
  isLoading: boolean
  error: string | null
  gameOver: boolean
  agentThought: string | null
  degraded: boolean
  debugVisible: boolean
  saves: SaveInfo[]
  savePanelVisible: boolean
  startGame: (playerName: string, spiritRootType?: SpiritRootType) => Promise<void>
  chooseAction: (choiceId: string) => Promise<void>
  sendFreeInput: (text: string) => Promise<void>
  restartGame: () => void
  clearError: () => void
  toggleDebug: () => void
  openSavePanel: () => Promise<void>
  closeSavePanel: () => void
  saveGame: (label: string) => Promise<void>
  loadGame: (saveId: string) => Promise<void>
}

function fallbackSegments(text: string): NarrativeSegment[] {
  return [{ type: 'narration', text }]
}

export const useGameStore = create<GameStore>((set, get) => ({
  gameState: null,
  narrativeSegments: [],
  availableChoices: [],
  freeInputEnabled: false,
  isLoading: false,
  error: null,
  gameOver: false,
  agentThought: null,
  degraded: false,
  debugVisible: false,
  saves: [],
  savePanelVisible: false,

  async startGame(playerName, spiritRootType) {
    const cleanName = playerName.trim()
    if (!cleanName) {
      set({ error: '请输入角色姓名。' })
      return
    }

    set({ isLoading: true, error: null, gameOver: false, agentThought: null, degraded: false })

    try {
      const response = await gameApi.startSession({
        player_name: cleanName,
        spirit_root_type: spiritRootType,
      })

      set({
        gameState: response.initial_state,
        narrativeSegments:
          response.narrative_segments ?? fallbackSegments(response.opening_narrative),
        availableChoices: response.available_choices ?? [],
        freeInputEnabled: response.free_input_enabled ?? true,
        degraded: false,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '开始游戏失败',
      })
    }
  },

  async chooseAction(choiceId) {
    const { gameState, isLoading } = get()
    if (!gameState || isLoading) return

    set({ isLoading: true, error: null })

    try {
      const response = await gameApi.submitAction(gameState.session_id, {
        action_type: 'choice',
        payload: choiceId,
      })

      set({
        gameState: response.new_state,
        narrativeSegments:
          response.narrative_segments?.length > 0
            ? response.narrative_segments
            : fallbackSegments(response.narrative),
        availableChoices: response.available_choices,
        freeInputEnabled: response.free_input_enabled,
        gameOver: response.game_over,
        agentThought: response.agent_thought ?? null,
        degraded: response.degraded ?? false,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '提交选择失败',
      })
    }
  },

  async sendFreeInput(text) {
    const { gameState, isLoading, freeInputEnabled } = get()
    const cleanText = text.trim()

    if (!gameState || isLoading || !freeInputEnabled) return
    if (!cleanText) {
      set({ error: '请输入你想说的话或想做的事。' })
      return
    }

    set({ isLoading: true, error: null })

    try {
      const response = await gameApi.submitAction(gameState.session_id, {
        action_type: 'free_input',
        payload: cleanText,
      })

      set({
        gameState: response.new_state,
        narrativeSegments:
          response.narrative_segments?.length > 0
            ? response.narrative_segments
            : fallbackSegments(response.narrative),
        availableChoices: response.available_choices,
        freeInputEnabled: response.free_input_enabled,
        gameOver: response.game_over,
        agentThought: response.agent_thought ?? null,
        degraded: response.degraded ?? false,
        isLoading: false,
      })
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '发送自由输入失败',
      })
    }
  },

  restartGame() {
    gameApi.resetMock()
    set({
      gameState: null,
      narrativeSegments: [],
      availableChoices: [],
      freeInputEnabled: false,
      isLoading: false,
      error: null,
      gameOver: false,
      agentThought: null,
      degraded: false,
      debugVisible: false,
      saves: [],
      savePanelVisible: false,
    })
  },

  clearError() {
    set({ error: null })
  },

  toggleDebug() {
    set((state) => ({ debugVisible: !state.debugVisible }))
  },

  async openSavePanel() {
    const { gameState } = get()
    if (!gameState) return
    set({ savePanelVisible: true, isLoading: true, error: null })
    try {
      const saves = await gameApi.getSaves(gameState.session_id)
      set({ saves: [...saves].reverse(), isLoading: false })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '读取存档失败' })
    }
  },

  closeSavePanel() {
    set({ savePanelVisible: false })
  },

  async saveGame(label) {
    const { gameState } = get()
    if (!gameState) return
    set({ isLoading: true, error: null })
    try {
      await gameApi.saveGame(gameState.session_id, label)
      const saves = await gameApi.getSaves(gameState.session_id)
      set({ saves: [...saves].reverse(), isLoading: false })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '保存游戏失败' })
    }
  },

  async loadGame(saveId) {
    const { gameState } = get()
    if (!gameState) return
    set({ isLoading: true, error: null })
    try {
      const loadedState = await gameApi.loadGame(gameState.session_id, saveId)
      set({
        gameState: loadedState,
        gameOver: false,
        savePanelVisible: false,
        narrativeSegments: fallbackSegments('存档已载入。你重新凝神，继续眼前的仙途。'),
        degraded: false,
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '载入存档失败' })
    }
  },
}))
