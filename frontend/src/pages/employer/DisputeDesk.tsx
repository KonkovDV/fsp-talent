import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, decideDispute, deskDispute, deskDisputes, type DeskDispute } from '../../api/client'
import { Empty, date } from '../../components/ui'
import { gradeRu, ROLE_RU } from '../../labels'

const NOTE_MIN = 10
const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)} %`)

function Attempt({ row }: { row: DeskDispute }) {
  const a = row.attempt
  if (!a) return <p className="text-sm text-ink-3">Попытка удалена вместе с аккаунтом.</p>
  return (
    <p className="text-sm text-ink-2">
      {a.specialization ? (ROLE_RU[a.specialization] ?? a.specialization) : '—'}, {gradeRu(a.target_grade)}:
      {' '}заданий {a.items_count ?? '—'}, вероятность уровня {pct(a.p_pass)}
      {a.duration_s != null && `, ${Math.round(a.duration_s / 60)} мин`}
      {a.integrity_level !== 'none' && `, сигналы честности: ${a.integrity_signals.length}`}
      {a.person_fit_review && ', ответы плохо сходятся с моделью'}
    </p>
  )
}

function Detail({ id, onDone }: { id: string; onDone: () => void }) {
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const { data, isLoading } = useQuery({ queryKey: ['deskDispute', id], queryFn: () => deskDispute(id).then(r => r.data) })
  const decide = useMutation({
    mutationFn: (action: 'uphold' | 'void') => decideDispute(id, action, note),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['deskDisputes'] })
      onDone()
    },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось сохранить решение')),
  })
  if (isLoading || !data) return <p className="text-sm text-ink-3">Загружаем попытку…</p>
  const ready = note.trim().length >= NOTE_MIN && !decide.isPending
  return (
    <div className="mt-3 space-y-3">
      <ol className="space-y-2 text-sm">
        {data.items.map(it => (
          <li key={it.seq} className="panel-quiet">
            <p className="text-xs text-ink-3">#{it.seq} · {it.family_id}, уровень {it.level}
              {it.spent_s != null && ` · ${it.spent_s} с из ${it.time_limit_s}`}{it.timed_out && ' · время вышло'}
              {it.excluded && ' · исключено из оценки'}</p>
            <p className="text-ink">{it.stem}</p>
            {it.code && <pre className="mt-1 overflow-x-auto text-xs">{it.code}</pre>}
            <p className="text-ink-2">Ответ: {it.given ?? '—'} · верно: {it.right ?? '—'} · {it.correct ? 'засчитан' : 'не засчитан'}</p>
          </li>
        ))}
      </ol>
      <label className="block text-sm" htmlFor={`note-${id}`}>Ответ кандидату</label>
      <textarea id={`note-${id}`} className="input min-h-20" maxLength={1000} value={note} onChange={e => setNote(e.target.value)}
        placeholder="Что проверено и почему так решено. Без имён и контактов." />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary btn-sm" disabled={!ready} onClick={() => decide.mutate('uphold')}>Оставить результат</button>
        <button type="button" className="btn-secondary btn-sm" disabled={!ready || !data.attempt?.voidable}
          onClick={() => decide.mutate('void')}
          title={data.attempt?.voidable ? undefined : 'Аннулировать можно только тест на грейд, который грейд не подтвердил'}>
          Аннулировать попытку
        </button>
      </div>
      <p className="text-xs text-ink-3">Грейд здесь не ставится. Аннулированная попытка не мешает пересдаче и не опускает грейд в подборке.</p>
      {error && <p className="notice-error" role="alert">{error}</p>}
    </div>
  )
}

/** Disputed results: the oldest first, with the 30-day deadline of 152-FZ art. 16. */
export default function DisputeDesk() {
  const [open, setOpen] = useState<string | null>(null)
  const { data = [], isLoading } = useQuery({ queryKey: ['deskDisputes'], queryFn: () => deskDisputes('open').then(r => r.data) })
  return (
    <section aria-labelledby="desk-disputes">
      <h2 id="desk-disputes" className="mb-3 mt-8 font-display text-xl font-bold text-ink">Обращения по тесту</h2>
      {!isLoading && data.length === 0 && (
        <Empty title="Открытых обращений нет">Кандидат оспаривает законченный тест кнопкой на странице результата. Ответ — в течение 30 дней.</Empty>
      )}
      <ul className="space-y-2">
        {data.map(row => (
          <li key={row.id} className="card text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-ink">Обращение от {date(row.created_at)}</span>
              <span className={row.overdue ? 'font-medium text-danger' : 'text-ink-3'}>
                {row.overdue ? 'срок ответа прошёл' : `ответить до ${date(row.due_at)}`}
              </span>
            </div>
            <Attempt row={row} />
            {row.reason && <p className="text-ink-2">Кандидат пишет: {row.reason}</p>}
            {open === row.id
              ? <Detail id={row.id} onDone={() => setOpen(null)} />
              : <button type="button" className="btn-ghost btn-sm mt-2" onClick={() => setOpen(row.id)}>Открыть попытку</button>}
          </li>
        ))}
      </ul>
    </section>
  )
}
