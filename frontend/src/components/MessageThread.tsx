import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, listMessages, postMessage } from '../api/client'

const time = (iso: string) => new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

/** Messages of one accepted invitation. Opening the thread marks the other side's messages as read. */
export default function MessageThread({ offerId, listKey, other }: { offerId: string; listKey: string; other: string }) {
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const end = useRef<HTMLLIElement>(null)
  const { data, isLoading } = useQuery({
    queryKey: ['thread', offerId], queryFn: () => listMessages(offerId).then(r => r.data), refetchInterval: 15_000,
  })
  useEffect(() => { qc.invalidateQueries({ queryKey: [listKey] }) }, [data?.messages.length, listKey, qc])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [data?.messages.length])
  const send = useMutation({
    mutationFn: () => postMessage(offerId, text.trim()),
    onSuccess: () => { setText(''); setError(''); qc.invalidateQueries({ queryKey: ['thread', offerId] }) },
    onError: e => setError(apiError(e, 'Сообщение не отправлено')),
  })
  const messages = data?.messages ?? []
  return (
    <div className="mt-4 rounded-lg border border-line bg-sunken/60 p-4" data-testid="thread">
      {isLoading && <p className="text-sm text-ink-3">Загружаем переписку…</p>}
      {!isLoading && messages.length === 0 && <p className="text-sm text-ink-2">Сообщений пока нет. Напишите первым: договоритесь о созвоне или задайте вопрос.</p>}
      <ul className="max-h-72 space-y-2 overflow-y-auto" aria-label="Сообщения">
        {messages.map(m => (
          <li key={m.id} className={`flex ${m.mine ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.mine ? 'bg-accent text-accent-ink' : 'border border-line bg-panel text-ink'}`}>
              <p className="whitespace-pre-wrap break-words">{m.body}</p>
              <p className={`mt-1 text-2xs ${m.mine ? 'text-accent-ink/80' : 'text-ink-3'}`}>{m.mine ? 'Вы' : other}, {time(m.created_at)}</p>
            </div>
          </li>
        ))}
        <li ref={end} aria-hidden />
      </ul>
      {data?.can_post ? (
        <form onSubmit={e => { e.preventDefault(); if (text.trim()) send.mutate() }} className="mt-3 flex flex-col gap-2 sm:flex-row">
          <label htmlFor={`msg-${offerId}`} className="sr-only">Сообщение</label>
          <textarea id={`msg-${offerId}`} value={text} onChange={e => setText(e.target.value)} rows={2} maxLength={2000}
            className="input min-w-0 flex-1 resize-y" placeholder="Сообщение" />
          <button type="submit" disabled={!text.trim() || send.isPending} className="btn-primary self-end">Отправить</button>
        </form>
      ) : data && <p className="mt-3 text-xs text-ink-3">Кандидат закрыл контакты для компании: переписка только для чтения.</p>}
      {error && <p className="notice-error mt-2" role="alert">{error}</p>}
    </div>
  )
}
