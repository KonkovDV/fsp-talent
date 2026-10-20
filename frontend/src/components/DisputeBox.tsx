import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiError, disputeGrade } from '../api/client'
import { date } from './ui'

const REASON_MAX = 1000

/** «Оспорить результат»: a methodist answers within 30 days (152-FZ art. 16). The grade is never set by hand. */
export default function DisputeBox({ sessionId }: { sessionId: string }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState('')
  const [done, setDone] = useState<{ text: string; due: string } | null>(null)
  const [error, setError] = useState('')
  const send = useMutation({
    mutationFn: () => disputeGrade(sessionId, reason),
    onSuccess: r => {
      setError('')
      setDone({ text: r.data.text, due: r.data.due_at })
      qc.invalidateQueries({ queryKey: ['myDisputes'] })
    },
    onError: (e: unknown) => setError(apiError(e, 'Оспорить не удалось')),
  })
  if (done) {
    return (
      <div className="space-y-1" role="status">
        <p className="text-sm text-ink">{done.text}</p>
        <p className="text-sm text-ink-2">Ответ — не позднее {date(done.due)}, в разделе «Обращения» ниже.</p>
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <p className="text-sm text-ink-2">
        Результат теста влияет на подборку. Если что-то пошло не так, обращение рассмотрит методист:
        он видит попытку, но не ваше имя. Грейд вручную не ставится; неудачную попытку можно только аннулировать.
      </p>
      <label className="block text-sm" htmlFor={`dispute-${sessionId}`}>Что пошло не так (необязательно)</label>
      <textarea id={`dispute-${sessionId}`} className="input min-h-20" maxLength={REASON_MAX} value={reason}
        onChange={e => setReason(e.target.value)} placeholder="Например: задание не открылось, таймер сбросился. Без имени и контактов." />
      <button type="button" onClick={() => send.mutate()} disabled={send.isPending}
        className="btn-secondary btn-sm">Оспорить результат</button>
      {error && <p className="notice-error" role="alert">{error}</p>}
    </div>
  )
}
