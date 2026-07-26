import type { EventRecord, GameState } from '../types/game'

interface HistoryPanelProps {
  state: GameState
  onClose: () => void
}

function eventTitle(event: EventRecord): string {
  return event.turn === 0 ? '序章' : `第 ${event.turn} 回合`
}

export function HistoryPanel({ state, onClose }: HistoryPanelProps) {
  const events: EventRecord[] = state.recent_events.length > 0
    ? state.recent_events
    : [{
        turn: state.turn_count,
        scene_id: state.current_scene_id,
        narrative: state.narrative,
        player_choice: '',
        state_changes: {},
        timestamp: '',
      }]

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="剧情回顾">
      <section className="ink-panel flex max-h-[88vh] w-full max-w-3xl flex-col rounded-2xl border border-amber-100/20 shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-amber-100/10 px-5 py-4 sm:px-7">
          <div>
            <p className="text-[10px] tracking-[0.35em] text-amber-200/45">STORY ARCHIVE</p>
            <h2 className="mt-1 font-serif text-xl tracking-[0.18em] text-amber-50">剧情回顾</h2>
            <p className="mt-2 text-xs text-stone-500">共 {events.length} 段记录 · 当前第 {state.turn_count} 回合</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-stone-100/10 px-3 py-2 text-xs text-stone-300 transition hover:border-stone-100/25 hover:text-white">关闭</button>
        </header>

        <div className="story-scroll flex-1 space-y-5 overflow-y-auto px-5 py-5 sm:px-7">
          {events.map((event, index) => (
            <article key={`${event.turn}-${event.scene_id}-${index}`} className="relative border-l border-amber-200/20 pl-5">
              <span className="absolute -left-1 top-1 size-2 rounded-full bg-amber-200/65 shadow-[0_0_12px_rgba(253,230,138,0.45)]" />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-serif text-sm tracking-[0.15em] text-amber-100">{eventTitle(event)}</h3>
                <span className="text-[10px] text-stone-600">{event.scene_id}</span>
              </div>
              {event.player_choice && event.turn > 0 && (
                <p className="mt-2 rounded-lg bg-emerald-100/[0.045] px-3 py-2 text-xs text-emerald-100/65">你的行动：{event.player_choice}</p>
              )}
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-stone-300">{event.narrative}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
