import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { listNotifications, readAllNotifications, readNotification } from '../api/client'

interface Note { id: string; kind: string; title: string; body: string | null; link: string | null; created_at: string; read: boolean }

const when = (iso: string) => {
  const d = new Date(iso)
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'только что'
  if (mins < 60) return `${mins} мин назад`
  if (mins < 24 * 60) return `${Math.round(mins / 60)} ч назад`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/** The other side's move: invitations, answers, applications. Polls every 30 s while the tab is open. */
export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const { data } = useQuery<{ unread: number; items: Note[] }>({
    queryKey: ['notifications'], queryFn: () => listNotifications().then(r => r.data), refetchInterval: 30_000,
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['notifications'] })
  const read = useMutation({ mutationFn: (id: string) => readNotification(id), onSuccess: refresh })
  const readAll = useMutation({ mutationFn: () => readAllNotifications(), onSuccess: refresh })

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown); document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  const unread = data?.unread ?? 0
  const items = data?.items ?? []
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-haspopup="true"
        aria-label={unread ? `Уведомления: ${unread} новых` : 'Уведомления'} className="btn-nav relative h-9 w-9 p-0">
        <Bell size={16} aria-hidden />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-none text-accent-ink num">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="fixed inset-x-4 top-16 z-50 overflow-hidden sm:absolute sm:inset-x-auto sm:right-0 sm:top-11 sm:w-[22rem] rounded-lg border border-line bg-panel shadow-lg shadow-ink/5" role="dialog" aria-label="Уведомления">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <p className="text-sm font-semibold text-ink">Уведомления</p>
            {unread > 0 && <button type="button" onClick={() => readAll.mutate()} className="text-xs text-accent hover:underline">Прочитать все</button>}
          </div>
          {items.length === 0
            ? <p className="px-4 py-6 text-center text-sm text-ink-3">Пока пусто. Здесь появятся приглашения, ответы и отклики.</p>
            : (
              <ul className="max-h-96 divide-y divide-line overflow-y-auto">
                {items.map(n => (
                  <li key={n.id}>
                    <button type="button" className="block w-full px-4 py-3 text-left hover:bg-sunken"
                      onClick={() => { if (!n.read) read.mutate(n.id); setOpen(false); if (n.link) navigate(n.link) }}>
                      <span className="flex items-start gap-2">
                        <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${n.read ? 'bg-transparent' : 'bg-accent'}`} aria-hidden />
                        <span className="min-w-0">
                          <span className={`block text-sm ${n.read ? 'text-ink-2' : 'font-semibold text-ink'}`}>{n.title}</span>
                          {n.body && <span className="mt-0.5 line-clamp-2 block text-xs text-ink-3">{n.body}</span>}
                          <span className="mt-1 block text-2xs text-ink-3">{when(n.created_at)}</span>
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
        </div>
      )}
    </div>
  )
}
