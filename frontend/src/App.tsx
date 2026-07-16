import { gameApi } from './api/client'
import { ChoicePanel } from './components/ChoicePanel'
import { DebugPanel } from './components/DebugPanel'
import { ErrorNotice } from './components/ErrorNotice'
import { FreeInputBox } from './components/FreeInputBox'
import { GameHeader } from './components/GameHeader'
import { StartGamePanel } from './components/StartGamePanel'
import { StatusPanel } from './components/StatusPanel'
import { TextDisplay } from './components/TextDisplay'
import { useGameStore } from './stores/gameStore'

function App() {
  const gameState = useGameStore((state) => state.gameState)
  const narrativeSegments = useGameStore((state) => state.narrativeSegments)
  const availableChoices = useGameStore((state) => state.availableChoices)
  const freeInputEnabled = useGameStore((state) => state.freeInputEnabled)
  const isLoading = useGameStore((state) => state.isLoading)
  const error = useGameStore((state) => state.error)
  const gameOver = useGameStore((state) => state.gameOver)
  const agentThought = useGameStore((state) => state.agentThought)
  const debugVisible = useGameStore((state) => state.debugVisible)
  const startGame = useGameStore((state) => state.startGame)
  const chooseAction = useGameStore((state) => state.chooseAction)
  const sendFreeInput = useGameStore((state) => state.sendFreeInput)
  const restartGame = useGameStore((state) => state.restartGame)
  const clearError = useGameStore((state) => state.clearError)
  const toggleDebug = useGameStore((state) => state.toggleDebug)

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
      />

      {error && <ErrorNotice message={error} onClose={clearError} />}

      {!gameState ? (
        <StartGamePanel isLoading={isLoading} onStart={startGame} />
      ) : (
        <main className="relative z-10 mx-auto grid max-w-[1500px] grid-cols-1 gap-4 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-5 lg:px-6 lg:py-6">
          <div className="min-w-0 space-y-4">
            <TextDisplay
              segments={narrativeSegments}
              isLoading={isLoading}
              gameOver={gameOver}
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

          <StatusPanel state={gameState} />
        </main>
      )}
    </div>
  )
}

export default App
