import { useEffect, useMemo, useState } from 'react'
import type { NarrativeSegment } from '../types/game'

interface TextDisplayProps {
  segments: NarrativeSegment[]
  isLoading: boolean
  gameOver: boolean
}

export function TextDisplay({ segments, isLoading, gameOver }: TextDisplayProps) {
  const contentKey = useMemo(() => JSON.stringify(segments), [segments])

  return (
    <TypingTextDisplay
      key={contentKey}
      segments={segments}
      isLoading={isLoading}
      gameOver={gameOver}
    />
  )
}

function TypingTextDisplay({ segments, isLoading, gameOver }: TextDisplayProps) {
  const totalCharacters = useMemo(
    () => segments.reduce((total, segment) => total + segment.text.length, 0),
    [segments],
  )
  const [visibleCharacters, setVisibleCharacters] = useState(0)

  useEffect(() => {
    if (totalCharacters === 0) return

    const timer = window.setInterval(() => {
      setVisibleCharacters((current) => {
        const next = current + 2
        if (next >= totalCharacters) {
          window.clearInterval(timer)
          return totalCharacters
        }
        return next
      })
    }, 22)

    return () => window.clearInterval(timer)
  }, [totalCharacters])

  const displayedSegments = segments.map((segment, index) => {
    const precedingCharacters = segments
      .slice(0, index)
      .reduce((total, item) => total + item.text.length, 0)
    const visibleLength = Math.max(0, visibleCharacters - precedingCharacters)
    const visibleText = segment.text.slice(0, visibleLength)
    return { ...segment, text: visibleText }
  })

  const typingFinished = visibleCharacters >= totalCharacters

  return (
    <section className="ink-panel relative flex min-h-[430px] flex-col overflow-hidden rounded-2xl border border-amber-100/15 p-5 sm:min-h-[500px] sm:p-8">
      <div className="pointer-events-none absolute right-6 top-4 select-none font-serif text-7xl text-amber-100/[0.035] sm:text-9xl">
        道
      </div>

      <div className="mb-6 flex items-center justify-between border-b border-amber-100/10 pb-4">
        <div>
          <p className="text-[10px] tracking-[0.35em] text-amber-200/45">NARRATIVE</p>
          <h2 className="mt-1 font-serif text-lg tracking-[0.18em] text-amber-50">仙途纪事</h2>
        </div>

        {!typingFinished && totalCharacters > 0 && (
          <button
            type="button"
            onClick={() => setVisibleCharacters(totalCharacters)}
            className="rounded-lg border border-amber-100/10 px-3 py-1.5 text-xs text-stone-400 transition hover:border-amber-100/25 hover:text-amber-50"
          >
            显示全文
          </button>
        )}
      </div>

      <div className="relative flex-1 space-y-5 overflow-y-auto pr-1 text-[15px] leading-8 text-stone-200 sm:text-base sm:leading-9">
        {displayedSegments.map((segment, index) => {
          if (!segment.text) return null

          if (segment.type === 'dialogue') {
            return (
              <div
                key={`${segment.speaker ?? 'npc'}-${index}`}
                className="rounded-xl border-l-2 border-amber-300/50 bg-amber-100/[0.045] px-4 py-3"
              >
                <p className="mb-1 text-xs tracking-[0.18em] text-amber-200/65">
                  {segment.speaker ?? '未知之人'}
                </p>
                <p className="text-amber-50/95">“{segment.text}”</p>
              </div>
            )
          }

          return (
            <p key={`narration-${index}`} className="indent-8 text-stone-200/90">
              {segment.text}
            </p>
          )
        })}

        {isLoading && (
          <div className="flex items-center gap-2 py-3 text-sm text-amber-100/50">
            <span className="loading-dot" />
            <span className="loading-dot [animation-delay:160ms]" />
            <span className="loading-dot [animation-delay:320ms]" />
            <span className="ml-2">天机推演中</span>
          </div>
        )}

        {gameOver && typingFinished && (
          <div className="mx-auto mt-8 max-w-md border-y border-amber-200/15 py-5 text-center">
            <p className="font-serif text-xl tracking-[0.3em] text-amber-100">第一卷 · 山门初启</p>
            <p className="mt-3 text-sm text-stone-400">MVP 主线体验完成</p>
          </div>
        )}
      </div>
    </section>
  )
}
