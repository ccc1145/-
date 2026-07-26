import { useEffect } from 'react'
import type { StateNotification } from '../types/game'

interface StateNotificationsProps {
  notifications: StateNotification[]
  onDismiss: (id: number) => void
}

function NotificationItem({ notification, onDismiss }: { notification: StateNotification; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(notification.id), 3600)
    return () => window.clearTimeout(timer)
  }, [notification.id, onDismiss])

  const toneClass = notification.tone === 'positive'
    ? 'border-emerald-300/30 text-emerald-50'
    : notification.tone === 'negative'
      ? 'border-red-300/30 text-red-50'
      : 'border-amber-200/25 text-amber-50'

  return (
    <button type="button" onClick={() => onDismiss(notification.id)} className={`state-toast w-full rounded-xl border bg-[#0b1613]/95 px-4 py-3 text-left shadow-2xl backdrop-blur-xl ${toneClass}`}>
      <span className="block text-[10px] tracking-[0.2em] opacity-55">{notification.label}</span>
      <span className="status-text-flash mt-1 block text-sm font-medium">{notification.detail}</span>
    </button>
  )
}

export function StateNotifications({ notifications, onDismiss }: StateNotificationsProps) {
  if (notifications.length === 0) return null
  return (
    <div className="fixed right-4 top-20 z-50 w-[min(22rem,calc(100%-2rem))] space-y-2" aria-live="polite">
      {notifications.map((notification) => <NotificationItem key={notification.id} notification={notification} onDismiss={onDismiss} />)}
    </div>
  )
}
