import { create } from 'zustand'
import { gameApi } from '../api/client'
import type {
  Choice,
  GameState,
  NarrativeSegment,
  SaveInfo,
  StateNotification,
  SpiritRootType,
} from '../types/game'

interface GameStore {
  username: string | null
  authLoading: boolean
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
  historyVisible: boolean
  notifications: StateNotification[]
  restoreAuth: () => Promise<void>
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
  startGame: (playerName: string, spiritRootType?: SpiritRootType) => Promise<void>
  chooseAction: (choiceId: string) => Promise<void>
  sendFreeInput: (text: string) => Promise<void>
  restartGame: () => void
  clearError: () => void
  toggleDebug: () => void
  openSavePanel: () => Promise<void>
  closeSavePanel: () => void
  openHistory: () => void
  closeHistory: () => void
  dismissNotification: (id: number) => void
  saveGame: (label: string) => Promise<void>
  loadGame: (saveId: string) => Promise<void>
  deleteSave: (saveId: string) => Promise<void>
}

function fallbackSegments(text: string): NarrativeSegment[] {
  return [{ type: 'narration', text }]
}

// Prevent a slow response from an abandoned playthrough from restoring stale state.
let lifecycleVersion = 0
let notificationId = 0

function stateNotifications(previous: GameState, next: GameState): StateNotification[] {
  const messages: Omit<StateNotification, 'id'>[] = []
  const addDelta = (label: string, before: number | null, after: number | null) => {
    if (before === null || after === null || before === after) return
    const delta = after - before
    messages.push({ label, detail: `${delta > 0 ? '+' : ''}${delta}（当前 ${after}）`, tone: delta > 0 ? 'positive' : 'negative' })
  }

  addDelta('修为变化', previous.player.cultivation, next.player.cultivation)
  addDelta('生命变化', previous.player.hp, next.player.hp)
  addDelta('灵力变化', previous.player.mp, next.player.mp)
  addDelta('灵石变化', previous.player.spirit_stones, next.player.spirit_stones)

  if (previous.player.realm.major !== next.player.realm.major || previous.player.realm.minor !== next.player.realm.minor) {
    messages.push({ label: '境界突破', detail: `${next.player.realm.major} ${next.player.realm.minor} 层`, tone: 'positive' })
  }

  for (const [npcId, npc] of Object.entries(next.npcs)) {
    const before = previous.npcs[npcId]?.affinity ?? npc.affinity
    if (before !== npc.affinity) addDelta(`${npc.name}好感`, before, npc.affinity)
  }

  const previousItems = new Map(previous.player.inventory.map((item) => [item.item_id, item]))
  const nextItems = new Map(next.player.inventory.map((item) => [item.item_id, item]))
  for (const [itemId, item] of nextItems) {
    const before = previousItems.get(itemId)?.quantity ?? 0
    if (before !== item.quantity) {
      const delta = item.quantity - before
      messages.push({ label: delta > 0 ? '获得道具' : '道具变化', detail: `${item.name} ${delta > 0 ? '+' : ''}${delta}（现有 ${item.quantity}）`, tone: delta > 0 ? 'positive' : 'negative' })
    }
  }
  for (const [itemId, item] of previousItems) {
    if (!nextItems.has(itemId)) messages.push({ label: '消耗道具', detail: `${item.name} -${item.quantity}`, tone: 'negative' })
  }

  if (previous.world.current_location !== next.world.current_location) {
    messages.push({ label: '地点变更', detail: next.world.current_location, tone: 'neutral' })
  }
  return messages.map((message) => ({ ...message, id: ++notificationId }))
}

export const useGameStore = create<GameStore>((set, get) => ({
  username: null,
  authLoading: true,
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
  historyVisible: false,
  notifications: [],

  async restoreAuth() {
    const username = await gameApi.restoreAuth()
    set({ username, authLoading: false })
  },

  async login(username, password) {
    set({ authLoading: true, error: null })
    try {
      const response = await gameApi.login(username.trim(), password)
      set({ username: response.username, authLoading: false })
    } catch (error) {
      set({ authLoading: false, error: error instanceof Error ? error.message : '登录失败' })
    }
  },

  async register(username, password) {
    set({ authLoading: true, error: null })
    try {
      const response = await gameApi.register(username.trim(), password)
      set({ username: response.username, authLoading: false })
    } catch (error) {
      set({ authLoading: false, error: error instanceof Error ? error.message : '注册失败' })
    }
  },

  logout() {
    lifecycleVersion += 1
    gameApi.logout()
    set({
      username: null,
      gameState: null,
      narrativeSegments: [],
      availableChoices: [],
      saves: [],
      savePanelVisible: false,
      historyVisible: false,
      notifications: [],
      error: null,
    })
  },

  async startGame(playerName, spiritRootType) {
    const cleanName = playerName.trim()
    if (!cleanName) {
      set({ error: '请输入角色姓名。' })
      return
    }

    const requestVersion = ++lifecycleVersion
    set({
      gameState: null,
      narrativeSegments: [],
      availableChoices: [],
      freeInputEnabled: false,
      isLoading: true,
      error: null,
      gameOver: false,
      agentThought: null,
      degraded: false,
      saves: [],
      savePanelVisible: false,
      historyVisible: false,
      notifications: [],
    })

    try {
      const response = await gameApi.startSession({
        player_name: cleanName,
        spirit_root_type: spiritRootType,
      })

      if (requestVersion !== lifecycleVersion) return

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
      if (requestVersion !== lifecycleVersion) return
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '开始游戏失败',
      })
    }
  },

  async chooseAction(choiceId) {
    const { gameState, isLoading } = get()
    if (!gameState || isLoading) return
    const requestVersion = lifecycleVersion
    const sessionId = gameState.session_id

    set({ isLoading: true, error: null })

    try {
      const response = await gameApi.submitAction(gameState.session_id, {
        action_type: 'choice',
        payload: choiceId,
      })

      if (
        requestVersion !== lifecycleVersion ||
        get().gameState?.session_id !== sessionId
      ) return

      set({
        gameState: response.new_state,
        notifications: stateNotifications(gameState, response.new_state),
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
      if (requestVersion !== lifecycleVersion) return
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
    const requestVersion = lifecycleVersion
    const sessionId = gameState.session_id

    set({ isLoading: true, error: null })

    try {
      const response = await gameApi.submitAction(gameState.session_id, {
        action_type: 'free_input',
        payload: cleanText,
      })

      if (
        requestVersion !== lifecycleVersion ||
        get().gameState?.session_id !== sessionId
      ) return

      set({
        gameState: response.new_state,
        notifications: stateNotifications(gameState, response.new_state),
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
      if (requestVersion !== lifecycleVersion) return
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : '发送自由输入失败',
      })
    }
  },

  restartGame() {
    lifecycleVersion += 1
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
      historyVisible: false,
      notifications: [],
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
      set({ saves, isLoading: false })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '读取存档失败' })
    }
  },

  closeSavePanel() {
    set({ savePanelVisible: false })
  },

  openHistory() {
    set({ historyVisible: true })
  },

  closeHistory() {
    set({ historyVisible: false })
  },

  dismissNotification(id) {
    set((state) => ({ notifications: state.notifications.filter((item) => item.id !== id) }))
  },

  async saveGame(label) {
    const { gameState } = get()
    if (!gameState) return
    set({ isLoading: true, error: null })
    try {
      const normalizedLabel = label.trim() || `第 ${gameState.turn_count} 回合`
      await gameApi.saveGame(gameState.session_id, normalizedLabel)
      const saves = await gameApi.getSaves(gameState.session_id)
      set({ saves, isLoading: false })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '保存游戏失败' })
    }
  },

  async loadGame(saveId) {
    const { gameState } = get()
    if (!gameState) return
    set({ isLoading: true, error: null })
    try {
      const response = await gameApi.loadGame(gameState.session_id, saveId)
      set({
        gameState: response.state,
        notifications: stateNotifications(gameState, response.state),
        availableChoices: response.available_choices,
        freeInputEnabled: response.free_input_enabled,
        gameOver: response.game_over,
        savePanelVisible: false,
        narrativeSegments: fallbackSegments('存档已载入。你重新凝神，继续眼前的仙途。'),
        degraded: false,
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '载入存档失败' })
    }
  },

  async deleteSave(saveId) {
    const { gameState } = get()
    if (!gameState) return
    set({ isLoading: true, error: null })
    try {
      await gameApi.deleteSave(gameState.session_id, saveId)
      set((state) => ({
        saves: state.saves.filter((save) => save.save_id !== saveId),
        isLoading: false,
      }))
    } catch (error) {
      set({ isLoading: false, error: error instanceof Error ? error.message : '删除存档失败' })
    }
  },
}))
