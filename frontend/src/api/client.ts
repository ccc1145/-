import axios from 'axios'
import { mockApi } from './mock'
import type {
  ActionRequest,
  ActionResponse,
  AuthResponse,
  GameState,
  LoadGameResponse,
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

const TOKEN_KEY = 'xiuxian_auth_token'
const savedToken = localStorage.getItem(TOKEN_KEY)
if (savedToken) http.defaults.headers.common.Authorization = `Bearer ${savedToken}`

function applyToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
    http.defaults.headers.common.Authorization = `Bearer ${token}`
  } else {
    localStorage.removeItem(TOKEN_KEY)
    delete http.defaults.headers.common.Authorization
  }
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: string; message?: string; error?: string }
      | undefined
    return data?.detail ?? data?.message ?? data?.error ?? error.message ?? '网络请求失败'
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

  async register(username: string, password: string): Promise<AuthResponse> {
    try {
      const response = await http.post<AuthResponse>('/auth/register', { username, password })
      applyToken(response.data.token)
      return response.data
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async login(username: string, password: string): Promise<AuthResponse> {
    try {
      const response = await http.post<AuthResponse>('/auth/login', { username, password })
      applyToken(response.data.token)
      return response.data
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async restoreAuth(): Promise<string | null> {
    if (!localStorage.getItem(TOKEN_KEY)) return null
    try {
      const response = await http.get<{ username: string }>('/auth/me')
      return response.data.username
    } catch {
      applyToken(null)
      return null
    }
  },

  logout(): void {
    applyToken(null)
  },

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

  async loadGame(sessionId: string, saveId: string): Promise<LoadGameResponse> {
    try {
      if (USE_MOCK) return await mockApi.loadGame(sessionId, saveId)
      const response = await http.post<LoadGameResponse>(`/session/${sessionId}/load`, {
        save_id: saveId,
      })
      return response.data
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  async deleteSave(sessionId: string, saveId: string): Promise<void> {
    try {
      if (USE_MOCK) return await mockApi.deleteSave(sessionId, saveId)
      await http.delete(`/session/${sessionId}/saves/${saveId}`)
    } catch (error) {
      throw new Error(getErrorMessage(error), { cause: error })
    }
  },

  resetMock(): void {
    if (USE_MOCK) mockApi.reset()
  },
}
