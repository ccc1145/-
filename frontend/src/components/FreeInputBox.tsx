import { useState } from 'react'

interface FreeInputBoxProps {
  disabled: boolean
  enabled: boolean
  onSend: (text: string) => Promise<void>
}

export function FreeInputBox({ disabled, enabled, onSend }: FreeInputBoxProps) {
  const [text, setText] = useState('')
  const [isComposing, setIsComposing] = useState(false)

  const send = async () => {
    const cleanText = text.trim()
    if (!cleanText || disabled || !enabled) return
    setText('')
    await onSend(cleanText)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !isComposing) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <section className="ink-panel rounded-2xl border border-amber-100/15 p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm tracking-[0.18em] text-amber-50/90">自由行动</h2>
          <p className="mt-1 text-xs text-stone-500">可输入对话、动作或你想尝试的事情</p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-[10px] ${
            enabled
              ? 'border-emerald-300/15 bg-emerald-300/5 text-emerald-200/60'
              : 'border-stone-300/10 text-stone-500'
          }`}
        >
          {enabled ? '当前可用' : '当前禁用'}
        </span>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <textarea
          value={text}
          onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          rows={2}
          maxLength={200}
          disabled={disabled || !enabled}
          placeholder={enabled ? '例如：弟子想请教如何感应天地灵气……' : '当前场景无法自由行动'}
          className="min-h-20 flex-1 resize-none rounded-xl border border-stone-100/10 bg-black/20 px-4 py-3 text-sm leading-6 text-stone-100 outline-none transition placeholder:text-stone-600 focus:border-amber-200/35 focus:bg-black/30 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="button"
          disabled={disabled || !enabled || !text.trim()}
          onClick={() => void send()}
          className="rounded-xl border border-amber-200/25 bg-amber-100/10 px-6 py-3 text-sm tracking-[0.18em] text-amber-50 transition hover:border-amber-100/50 hover:bg-amber-100/15 disabled:cursor-not-allowed disabled:opacity-40 sm:w-28"
        >
          发送
        </button>
      </div>
      <p className="mt-2 text-right text-[10px] text-stone-600">Enter 发送 · Shift + Enter 换行</p>
    </section>
  )
}
