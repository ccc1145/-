import { useEffect, useRef, useState } from 'react'

interface SpeechRecognitionAlternativeLike {
  transcript: string
}

interface SpeechRecognitionResultLike {
  isFinal: boolean
  length: number
  [index: number]: SpeechRecognitionAlternativeLike
}

interface SpeechRecognitionEventLike {
  resultIndex: number
  results: {
    length: number
    [index: number]: SpeechRecognitionResultLike
  }
}

interface SpeechRecognitionErrorEventLike {
  error: string
}

interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike

interface SpeechWindow extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
}

interface FreeInputBoxProps {
  disabled: boolean
  enabled: boolean
  onSend: (text: string) => Promise<void>
}

export function FreeInputBox({ disabled, enabled, onSend }: FreeInputBoxProps) {
  const [text, setText] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [speechError, setSpeechError] = useState('')
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const speechBaseTextRef = useRef('')

  const speechRecognitionConstructor =
    typeof window === 'undefined'
      ? undefined
      : (window as SpeechWindow).SpeechRecognition ??
        (window as SpeechWindow).webkitSpeechRecognition
  const speechSupported = Boolean(speechRecognitionConstructor)

  useEffect(() => {
    return () => recognitionRef.current?.abort()
  }, [])

  useEffect(() => {
    if ((disabled || !enabled) && recognitionRef.current) {
      recognitionRef.current.abort()
      recognitionRef.current = null
      setIsListening(false)
    }
  }, [disabled, enabled])

  const toggleSpeechInput = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      return
    }

    if (!speechRecognitionConstructor) {
      setSpeechError('当前浏览器不支持语音输入，请使用最新版 Chrome 或 Edge。')
      return
    }

    setSpeechError('')
    speechBaseTextRef.current = text.trimEnd()
    const recognition = new speechRecognitionConstructor()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        const transcript = result[0]?.transcript ?? ''
        if (result.isFinal) finalText += transcript
        else interimText += transcript
      }

      const spokenText = `${finalText}${interimText}`.trim()
      const prefix = speechBaseTextRef.current
      setText(`${prefix}${prefix && spokenText ? ' ' : ''}${spokenText}`.slice(0, 200))
      if (finalText.trim()) {
        speechBaseTextRef.current = `${prefix}${prefix ? ' ' : ''}${finalText.trim()}`.slice(0, 200)
      }
    }
    recognition.onerror = (event) => {
      const messages: Record<string, string> = {
        'not-allowed': '麦克风权限被拒绝，请在浏览器地址栏中允许使用麦克风。',
        'audio-capture': '没有检测到可用的麦克风。',
        'no-speech': '没有听清，请靠近麦克风后重试。',
        network: '语音识别服务暂时不可用，请检查网络后重试。',
      }
      setSpeechError(messages[event.error] ?? '语音识别失败，请重试。')
    }
    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
    }
    recognitionRef.current = recognition

    try {
      recognition.start()
      setIsListening(true)
    } catch {
      recognitionRef.current = null
      setSpeechError('无法启动语音输入，请稍后重试。')
    }
  }

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
        <div className="flex gap-2 sm:flex-col">
          <button
            type="button"
            disabled={disabled || !enabled || !speechSupported}
            onClick={toggleSpeechInput}
            aria-label={isListening ? '停止语音输入' : '开始语音输入'}
            aria-pressed={isListening}
            title={speechSupported ? '语音输入' : '当前浏览器不支持语音输入'}
            className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-2 text-xs transition sm:w-28 ${
              isListening
                ? 'border-red-300/45 bg-red-300/10 text-red-100'
                : 'border-stone-100/10 bg-black/15 text-stone-300 hover:border-amber-200/30 hover:text-amber-50'
            } disabled:cursor-not-allowed disabled:opacity-35`}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4 fill-none stroke-current" strokeWidth="1.8">
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v4M9 21h6" />
            </svg>
            {isListening ? '停止录音' : '语音输入'}
          </button>
          <button
            type="button"
            disabled={disabled || !enabled || !text.trim()}
            onClick={() => void send()}
            className="flex-1 rounded-xl border border-amber-200/25 bg-amber-100/10 px-6 py-3 text-sm tracking-[0.18em] text-amber-50 transition hover:border-amber-100/50 hover:bg-amber-100/15 disabled:cursor-not-allowed disabled:opacity-40 sm:w-28"
          >
            发送
          </button>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px]">
        <p className={speechError ? 'text-red-300/75' : isListening ? 'text-amber-200/75' : 'text-stone-600'}>
          {speechError || (isListening ? '正在聆听，说完后可再次点击停止……' : '语音内容识别后可编辑确认')}
        </p>
        <p className="text-stone-600">Enter 发送 · Shift + Enter 换行</p>
      </div>
    </section>
  )
}
