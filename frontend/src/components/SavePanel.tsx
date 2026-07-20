import { useState } from 'react'
import type { SaveInfo } from '../types/game'

interface SavePanelProps {
  saves: SaveInfo[]
  isLoading: boolean
  onClose: () => void
  onSave: (label: string) => Promise<void>
  onLoad: (saveId: string) => Promise<void>
}

export function SavePanel({ saves, isLoading, onClose, onSave, onLoad }: SavePanelProps) {
  const [label, setLabel] = useState('')

  async function handleSave() {
    await onSave(label)
    setLabel('')
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-panel-title"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section className="ink-panel w-full max-w-xl rounded-2xl border border-amber-100/15 p-5 shadow-2xl sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] tracking-[0.35em] text-amber-200/45">ARCHIVES</p>
            <h2 id="save-panel-title" className="mt-1 font-serif text-xl tracking-[0.18em] text-amber-50">
              洞天卷宗
            </h2>
          </div>
          <button type="button" onClick={onClose} className="px-2 text-2xl text-stone-400 hover:text-white" aria-label="关闭">
            ×
          </button>
        </div>

        <div className="mt-5 flex gap-2">
          <input
            value={label}
            onChange={(event) => setLabel(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && void handleSave()}
            placeholder="存档名称（可选）"
            maxLength={30}
            disabled={isLoading}
            className="min-w-0 flex-1 rounded-lg border border-amber-100/15 bg-black/20 px-3 py-2.5 text-sm text-amber-50 outline-none placeholder:text-stone-500 focus:border-amber-200/40"
          />
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isLoading}
            className="rounded-lg border border-amber-200/25 bg-amber-100/10 px-4 py-2 text-sm text-amber-100 transition hover:bg-amber-100/15 disabled:opacity-40"
          >
            保存当前进度
          </button>
        </div>

        <div className="mt-5 max-h-80 space-y-2 overflow-y-auto pr-1">
          {saves.length === 0 && !isLoading ? (
            <p className="rounded-xl border border-dashed border-stone-100/10 py-10 text-center text-sm text-stone-500">尚无存档</p>
          ) : (
            saves.map((save) => (
              <div key={save.save_id} className="flex items-center justify-between gap-3 rounded-xl border border-stone-100/10 bg-black/15 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-stone-100">{save.label}</p>
                  <time className="mt-1 block text-xs text-stone-500" dateTime={save.saved_at}>
                    {new Date(save.saved_at).toLocaleString('zh-CN')}
                  </time>
                </div>
                <button
                  type="button"
                  onClick={() => void onLoad(save.save_id)}
                  disabled={isLoading}
                  className="shrink-0 rounded-lg border border-emerald-200/20 px-3 py-1.5 text-xs text-emerald-100/80 hover:bg-emerald-100/10 disabled:opacity-40"
                >
                  载入
                </button>
              </div>
            ))
          )}
          {isLoading && <p className="py-5 text-center text-sm text-amber-100/50">卷宗整理中…</p>}
        </div>
      </section>
    </div>
  )
}
