import axios from 'axios'
import { mockApi } from './mock'
import type {
  ActionRequest,
  ActionResponse,
  GameState,
  SaveInfo,
  StartSessionRequest,
  StartSessionResponse,
} from '../types/game'

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { message?: string; error?: string } | undefined
    return data?.message ?? data?.error ?? error.message ?? '网络请求失败'
  }

  if (error instanceof Error) {
    return error.message
  }

  return '发生未知错误'
}

async function startRealSession(request: StartSessionRequest): Promise<StartSessionResponse> {
  const response = await http.post<StartSessionResponse>('/session/start', request)
  return response.data
}

async function submitRealAction(
  sessionId: string,
  request: ActionRequest,
): Promise<ActionResponse> {
  const response = await http.post<ActionResponse>(`/session/${sessionId}/action`, request)
  return response.data
}

export const gameApi = {
  isMockMode: USE_MOCK,

  async startSession(request: StartSessionRequest): Promise<StartSessionResponse> {
    try {
      return USE_MOCK ? await mockApi.startSession(request) : await startRealSession(request)
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async submitAction(sessionId: string, request: ActionRequest): Promise<ActionResponse> {
    try {
      return USE_MOCK
        ? await mockApi.submitAction(sessionId, request)
        : await submitRealAction(sessionId, request)
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async getState(sessionId: string): Promise<GameState> {
    try {
      const response = await http.get<{ state: GameState }>(`/session/${sessionId}/state`)
      return response.data.state
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async saveGame(sessionId: string, label: string): Promise<SaveInfo> {
    try {
      if (USE_MOCK) return await mockApi.saveGame(sessionId, label)
      const response = await http.post<SaveInfo>(`/session/${sessionId}/save`, { label })
      return response.data
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async getSaves(sessionId: string): Promise<SaveInfo[]> {
    try {
      if (USE_MOCK) return await mockApi.getSaves(sessionId)
      const response = await http.get<{ saves: SaveInfo[] }>(`/session/${sessionId}/saves`)
      return response.data.saves
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async loadGame(sessionId: string, saveId: string): Promise<GameState> {
    try {
      if (USE_MOCK) return await mockApi.loadGame(sessionId, saveId)
      const response = await http.post<{ state: GameState }>(`/session/${sessionId}/load`, {
        save_id: saveId,
      })
      return response.data.state
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  resetMock(): void {
    if (USE_MOCK) mockApi.reset()
  },
}
