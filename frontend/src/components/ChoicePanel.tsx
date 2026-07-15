import type { Choice } from '../types/game'

interface ChoicePanelProps {
  choices: Choice[]
  disabled: boolean
  gameOver: boolean
  onChoose: (choiceId: string) => Promise<void>
}

export function ChoicePanel({ choices, disabled, gameOver, onChoose }: ChoicePanelProps) {
  if (gameOver) {
    return (
      <section className="ink-panel rounded-2xl border border-amber-100/15 p-5 text-center text-sm text-stone-400">
        此段仙缘已经结束，可点击右上角“重新开局”再次体验。
      </section>
    )
  }

  return (
    <section className="ink-panel rounded-2xl border border-amber-100/15 p-4 sm:p-5">
      <div className="mb-4 flex items-center gap-3">
        <span className="h-px flex-1 bg-gradient-to-r from-transparent to-amber-100/15" />
        <h2 className="text-xs tracking-[0.25em] text-amber-100/60">择一而行</h2>
        <span className="h-px flex-1 bg-gradient-to-l from-transparent to-amber-100/15" />
      </div>

      {choices.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {choices.map((choice, index) => (
            <button
              key={choice.id}
              type="button"
              disabled={disabled || choice.disabled}
              onClick={() => void onChoose(choice.id)}
              className="choice-button group flex min-h-14 items-center gap-3 rounded-xl border border-stone-100/10 bg-black/15 px-4 py-3 text-left text-sm text-stone-200 transition hover:-translate-y-0.5 hover:border-amber-200/30 hover:bg-amber-100/[0.06] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-amber-200/20 text-xs text-amber-100/60 transition group-hover:border-amber-200/50 group-hover:text-amber-50">
                {index + 1}
              </span>
              <span className="leading-6">{choice.text}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="py-3 text-center text-sm text-stone-500">当前没有预设选项，可尝试自由输入。</p>
      )}
    </section>
  )
}
