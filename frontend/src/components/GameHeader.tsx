interface GameHeaderProps {
  isMockMode: boolean
  hasSession: boolean
  onRestart: () => void
  onToggleDebug: () => void
  onOpenSaves: () => void
}

export function GameHeader({
  isMockMode,
  hasSession,
  onRestart,
  onToggleDebug,
  onOpenSaves,
}: GameHeaderProps) {
  return (
    <header className="relative z-20 border-b border-amber-100/10 bg-[#08100e]/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div>
          <p className="text-[10px] tracking-[0.38em] text-amber-200/50">AI 文字生成游戏</p>
          <h1 className="mt-1 font-serif text-xl font-semibold tracking-[0.22em] text-amber-50 sm:text-2xl">
            修仙模拟器
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <span className="hidden rounded-full border border-emerald-300/15 bg-emerald-200/5 px-3 py-1.5 text-xs text-emerald-100/70 sm:inline-flex">
            {isMockMode ? 'Mock 演示模式' : '后端联调模式'}
          </span>

          {hasSession && (
            <>
              <button
                type="button"
                onClick={onOpenSaves}
                className="rounded-lg border border-stone-100/10 px-3 py-2 text-xs text-stone-300 transition hover:border-stone-100/25 hover:text-white"
              >
                存档
              </button>
              <button
                type="button"
                onClick={onToggleDebug}
                className="rounded-lg border border-stone-100/10 px-3 py-2 text-xs text-stone-300 transition hover:border-stone-100/25 hover:text-white"
              >
                调试
              </button>
              <button
                type="button"
                onClick={onRestart}
                className="rounded-lg border border-amber-200/20 px-3 py-2 text-xs text-amber-100/80 transition hover:border-amber-100/50 hover:bg-amber-100/10"
              >
                重新开局
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
