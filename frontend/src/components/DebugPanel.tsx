import type { GameState } from '../types/game'

interface DebugPanelProps {
  state: GameState
  thought: string | null
}

export function DebugPanel({ state, thought }: DebugPanelProps) {
  return (
    <section className="mt-4 rounded-2xl border border-cyan-300/15 bg-cyan-950/10 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs tracking-[0.22em] text-cyan-100/60">开发调试面板</h2>
        <span className="text-[10px] text-cyan-200/35">仅开发期展示</span>
      </div>
      {thought && (
        <p className="mb-3 rounded-lg border border-cyan-300/10 bg-black/20 px-3 py-2 text-xs leading-5 text-cyan-100/65">
          Agent thought：{thought}
        </p>
      )}
      <pre className="max-h-72 overflow-auto rounded-xl bg-black/25 p-3 text-[11px] leading-5 text-cyan-100/55">
        {JSON.stringify(state, null, 2)}
      </pre>
    </section>
  )
}
