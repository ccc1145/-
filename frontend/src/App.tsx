import { useEffect } from 'react'
import { gameApi } from './api/client'
import { AuthPanel } from './components/AuthPanel'
import { ChoicePanel } from './components/ChoicePanel'
import { DebugPanel } from './components/DebugPanel'
import { ErrorNotice } from './components/ErrorNotice'
import { FreeInputBox } from './components/FreeInputBox'
import { GameHeader } from './components/GameHeader'
import { HistoryPanel } from './components/HistoryPanel'
import { SavePanel } from './components/SavePanel'
import { StartGamePanel } from './components/StartGamePanel'
import { StatusPanel } from './components/StatusPanel'
import { StateNotifications } from './components/StateNotifications'
import { TextDisplay } from './components/TextDisplay'
import { useGameStore } from './stores/gameStore'
import type { StatusField } from './types/game'

function App() {
  const username = useGameStore((state) => state.username)
  const authLoading = useGameStore((state) => state.authLoading)
  const gameState = useGameStore((state) => state.gameState)
  const narrativeSegments = useGameStore((state) => state.narrativeSegments)
  const availableChoices = useGameStore((state) => state.availableChoices)
  const freeInputEnabled = useGameStore((state) => state.freeInputEnabled)
  const isLoading = useGameStore((state) => state.isLoading)
  const error = useGameStore((state) => state.error)
  const gameOver = useGameStore((state) => state.gameOver)
  const agentThought = useGameStore((state) => state.agentThought)
  const degraded = useGameStore((state) => state.degraded)
  const debugVisible = useGameStore((state) => state.debugVisible)
  const saves = useGameStore((state) => state.saves)
  const savePanelVisible = useGameStore((state) => state.savePanelVisible)
  const historyVisible = useGameStore((state) => state.historyVisible)
  const notifications = useGameStore((state) => state.notifications)
  const startGame = useGameStore((state) => state.startGame)
  const chooseAction = useGameStore((state) => state.chooseAction)
  const sendFreeInput = useGameStore((state) => state.sendFreeInput)
  const restartGame = useGameStore((state) => state.restartGame)
  const clearError = useGameStore((state) => state.clearError)
  const toggleDebug = useGameStore((state) => state.toggleDebug)
  const openSavePanel = useGameStore((state) => state.openSavePanel)
  const closeSavePanel = useGameStore((state) => state.closeSavePanel)
  const openHistory = useGameStore((state) => state.openHistory)
  const closeHistory = useGameStore((state) => state.closeHistory)
  const dismissNotification = useGameStore((state) => state.dismissNotification)
  const saveGame = useGameStore((state) => state.saveGame)
  const loadGame = useGameStore((state) => state.loadGame)
  const deleteSave = useGameStore((state) => state.deleteSave)
  const restoreAuth = useGameStore((state) => state.restoreAuth)
  const login = useGameStore((state) => state.login)
  const register = useGameStore((state) => state.register)
  const logout = useGameStore((state) => state.logout)
  const statusChangeIds = notifications.reduce<Partial<Record<StatusField, number>>>((fields, notification) => {
    fields[notification.statusField] = notification.id
    return fields
  }, {})

  useEffect(() => {
    void restoreAuth()
  }, [restoreAuth])

  return (
    <div className="app-shell min-h-screen text-stone-100">
      <div className="mountain-layer" aria-hidden="true" />
      <div className="mist mist-one" aria-hidden="true" />
      <div className="mist mist-two" aria-hidden="true" />

      <GameHeader
        isMockMode={gameApi.isMockMode}
        hasSession={Boolean(gameState)}
        onRestart={restartGame}
        onToggleDebug={toggleDebug}
        onOpenSaves={() => void openSavePanel()}
        onOpenHistory={openHistory}
        username={username}
        onLogout={logout}
      />

      {error && <ErrorNotice message={error} onClose={clearError} />}
      <StateNotifications notifications={notifications} onDismiss={dismissNotification} />

      {historyVisible && gameState && <HistoryPanel state={gameState} onClose={closeHistory} />}

      {savePanelVisible && (
        <SavePanel
          saves={saves}
          isLoading={isLoading}
          onClose={closeSavePanel}
          onSave={saveGame}
          onLoad={loadGame}
          onDelete={deleteSave}
        />
      )}

      {authLoading ? (
        <main className="relative z-10 flex min-h-[70vh] items-center justify-center text-amber-100/60">正在确认洞天身份……</main>
      ) : !username ? (
        <AuthPanel isLoading={authLoading} error={error} onLogin={login} onRegister={register} />
      ) : !gameState ? (
        <StartGamePanel isLoading={isLoading} onStart={startGame} />
      ) : (
        <main className="relative z-10 mx-auto grid max-w-[1500px] grid-cols-1 gap-4 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-5 lg:px-6 lg:py-6">
          <div className="min-w-0 space-y-4">
            <TextDisplay
              segments={narrativeSegments}
              isLoading={isLoading}
              gameOver={gameOver}
              degraded={degraded}
            />
            <ChoicePanel
              choices={availableChoices}
              disabled={isLoading}
              gameOver={gameOver}
              onChoose={chooseAction}
            />
            <FreeInputBox
              disabled={isLoading || gameOver}
              enabled={freeInputEnabled}
              onSend={sendFreeInput}
            />
            {debugVisible && <DebugPanel state={gameState} thought={agentThought} />}
          </div>

          <StatusPanel state={gameState} changeIds={statusChangeIds} />
        </main>
      )}
    </div>
  )
}

export default App
