import { useState } from 'react'
import type { SpiritRootType } from '../types/game'

interface StartGamePanelProps {
  isLoading: boolean
  onStart: (playerName: string, spiritRootType?: SpiritRootType) => Promise<void>
}

const spiritRoots: Array<{ value: SpiritRootType | ''; label: string }> = [
  { value: '', label: '天命随机' },
  { value: '金', label: '金灵根' },
  { value: '木', label: '木灵根' },
  { value: '水', label: '水灵根' },
  { value: '火', label: '火灵根' },
  { value: '土', label: '土灵根' },
]

export function StartGamePanel({ isLoading, onStart }: StartGamePanelProps) {
  const [playerName, setPlayerName] = useState('李逍遥')
  const [spiritRoot, setSpiritRoot] = useState<SpiritRootType | ''>('')

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await onStart(playerName, spiritRoot || undefined)
  }

  return (
    <main className="relative z-10 mx-auto flex min-h-[calc(100vh-74px)] max-w-6xl items-center justify-center px-4 py-10">
      <section className="ink-panel w-full max-w-xl overflow-hidden rounded-[28px] border border-amber-200/20 p-7 shadow-2xl shadow-black/50 sm:p-10">
        <div className="mb-8 text-center">
          <p className="mb-3 text-xs tracking-[0.45em] text-amber-200/60">青 云 问 道</p>
          <h2 className="font-serif text-4xl font-semibold tracking-[0.18em] text-amber-50 sm:text-5xl">
            踏入仙途
          </h2>
          <p className="mx-auto mt-5 max-w-md leading-7 text-stone-300/80">
            山门已开，钟声三响。留下你的名号，接受灵根试炼，走出属于自己的修仙之路。
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm tracking-[0.2em] text-amber-100/70">弟子名号</span>
            <input
              value={playerName}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => setPlayerName(event.target.value)}
              maxLength={12}
              className="w-full rounded-xl border border-amber-100/15 bg-black/20 px-4 py-3.5 text-lg text-stone-100 outline-none transition focus:border-amber-200/50 focus:bg-black/30"
              placeholder="请输入角色姓名"
              disabled={isLoading}
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm tracking-[0.2em] text-amber-100/70">灵根选择</span>
            <select
              value={spiritRoot}
              onChange={(event: React.ChangeEvent<HTMLSelectElement>) =>
                setSpiritRoot(event.target.value as SpiritRootType | '')
              }
              className="w-full rounded-xl border border-amber-100/15 bg-[#101a17] px-4 py-3.5 text-stone-100 outline-none transition focus:border-amber-200/50"
              disabled={isLoading}
            >
              {spiritRoots.map((root) => (
                <option key={root.label} value={root.value}>
                  {root.label}
                </option>
              ))}
            </select>
          </label>

          <button
            type="submit"
            disabled={isLoading || !playerName.trim()}
            className="group relative mt-3 w-full overflow-hidden rounded-xl border border-amber-200/30 bg-amber-100/10 px-5 py-4 text-base font-medium tracking-[0.25em] text-amber-50 transition hover:border-amber-100/60 hover:bg-amber-100/15 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <span className="relative z-10">{isLoading ? '推演命数中……' : '入山问道'}</span>
          </button>
        </form>
      </section>
    </main>
  )
}
