interface ErrorNoticeProps {
  message: string
  onClose: () => void
}

export function ErrorNotice({ message, onClose }: ErrorNoticeProps) {
  return (
    <div className="fixed left-1/2 top-20 z-50 flex w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 items-start gap-3 rounded-xl border border-red-300/30 bg-red-950/90 px-4 py-3 text-sm text-red-100 shadow-2xl backdrop-blur-xl">
      <span className="mt-0.5">⚠</span>
      <p className="flex-1 leading-6">{message}</p>
      <button type="button" onClick={onClose} className="text-red-100/60 hover:text-white">
        ×
      </button>
    </div>
  )
}
