import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError, assessmentBlueprint } from '../../api/client'
import { Empty, Skeleton, date } from '../../components/ui'

type Status = 'pending' | 'approved' | 'rejected'
interface Draft {
  id: string; spec: string; topic: string; level: number; stem: string; key: string
  status: Status; note: string | null; created_at: string; reviewed_at: string | null
}
interface Blueprint { specializations: Record<string, { label: string; topics: { topic: string; label: string }[] }> }

const TABS: [Status, string][] = [['pending', 'Ждут разбора'], ['approved', 'Одобрены'], ['rejected', 'Отклонены']]
const REASON: Record<string, string> = {
  disagree: 'Модели назвали разные ответы — черновик не сохранён.',
  leaked_in_stem: 'Ответ виден в условии — черновик не сохранён.',
  identity: 'В тексте нашлись имя, почта или телефон — черновик не сохранён.',
  model_error: 'Модель не ответила — черновик не сохранён.',
}

/** Model drafts that two models agreed on. A reviewed draft never enters the test. */
export default function ItemDrafts() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Status>('pending')
  const [spec, setSpec] = useState('backend')
  const [topic, setTopic] = useState('')
  const [level, setLevel] = useState(2)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [message, setMessage] = useState('')
  const blueprint = useQuery({ queryKey: ['assessmentBlueprint'], queryFn: () => assessmentBlueprint().then(r => r.data as Blueprint) })
  const list = useQuery({
    queryKey: ['itemDrafts', tab],
    queryFn: () => api.get<{ model_ready: boolean; items: Draft[] }>('/moderation/item-drafts', { params: { status: tab } }).then(r => r.data),
  })
  const topics = blueprint.data?.specializations[spec]?.topics ?? []
  const chosenTopic = topics.some(t => t.topic === topic) ? topic : topics[0]?.topic ?? ''
  const ask = useMutation({
    mutationFn: () => api.post<{ accepted: boolean; reason: string }>('/moderation/item-drafts', { spec, topic: chosenTopic, level }).then(r => r.data),
    onSuccess: data => {
      setMessage(data.accepted ? 'Черновик добавлен в очередь.' : REASON[data.reason] ?? 'Черновик не сохранён.')
      qc.invalidateQueries({ queryKey: ['itemDrafts'] })
    },
    onError: (e: unknown) => setMessage(apiError(e, 'Черновик не запрошен')),
  })
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: 'approved' | 'rejected' }) =>
      api.post(`/moderation/item-drafts/${id}/review`, { decision, note: notes[id]?.trim() || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['itemDrafts'] }),
    onError: (e: unknown) => setMessage(apiError(e, 'Решение не сохранено')),
  })

  return (
    <section className="mt-10 space-y-4" aria-labelledby="drafts-title">
      <div>
        <h2 id="drafts-title" className="font-display text-xl font-bold text-ink">Черновики заданий</h2>
        <p className="text-sm text-ink-2">
          Одна модель пишет задание, другая решает его, не видя ключа. В очередь попадает только черновик, где ответы совпали, а в тексте нет имён и контактов.
          Одобренный черновик — заготовка для автора семейства заданий. В тест он не попадает.
        </p>
      </div>
      {list.data && !list.data.model_ready && (
        <p className="notice-info text-sm" data-testid="drafts-off">Модели не подключены: нужны две разные модели GigaChat. Очередь можно разбирать, новые черновики не запрашиваются.</p>
      )}
      <form className="card flex flex-wrap items-end gap-3 p-4" onSubmit={e => { e.preventDefault(); setMessage(''); ask.mutate() }}>
        <label className="text-sm text-ink-2">Специализация
          <select className="input mt-1 block" value={spec} onChange={e => setSpec(e.target.value)}>
            {Object.entries(blueprint.data?.specializations ?? {}).map(([id, s]) => <option key={id} value={id}>{s.label}</option>)}
          </select>
        </label>
        <label className="text-sm text-ink-2">Тема
          <select className="input mt-1 block" value={chosenTopic} onChange={e => setTopic(e.target.value)}>
            {topics.map(t => <option key={t.topic} value={t.topic}>{t.label}</option>)}
          </select>
        </label>
        <label className="text-sm text-ink-2">Уровень
          <select className="input mt-1 block" value={level} onChange={e => setLevel(Number(e.target.value))}>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button type="submit" className="btn-primary btn-sm" disabled={ask.isPending || !list.data?.model_ready || !chosenTopic}>Запросить черновик</button>
      </form>
      {message && <p className="text-sm text-ink" role="status">{message}</p>}
      <div className="flex gap-2" role="tablist" aria-label="Статус черновиков">
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id}
            className={tab === id ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      {list.isLoading && <Skeleton className="h-32" />}
      {list.isError && <p className="notice-error" role="alert">{apiError(list.error, 'Очередь недоступна')}</p>}
      {list.data && list.data.items.length === 0 && <Empty title="Пусто">Здесь появятся черновики с этим статусом.</Empty>}
      <ul className="space-y-3">
        {list.data?.items.map(d => (
          <li key={d.id} className="card space-y-2" data-testid="draft">
            <p className="text-xs text-ink-3">{d.spec} · {d.topic} · уровень {d.level} · {date(d.created_at)}</p>
            <p className="whitespace-pre-wrap text-sm text-ink">{d.stem}</p>
            <p className="text-sm text-ink-2">Ответ обеих моделей: <span className="font-mono text-ink">{d.key}</span></p>
            {d.note && <p className="text-sm text-ink-2">Заметка: {d.note}</p>}
            {d.status === 'pending' && (
              <div className="flex flex-wrap items-center gap-2">
                <input className="input min-w-56 flex-1 text-sm" maxLength={500} placeholder="Заметка без имён и контактов"
                  aria-label="Заметка к черновику" value={notes[d.id] ?? ''} onChange={e => setNotes({ ...notes, [d.id]: e.target.value })} />
                <button type="button" className="btn-primary btn-sm" disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: d.id, decision: 'approved' })}>Одобрить</button>
                <button type="button" className="btn-secondary btn-sm" disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: d.id, decision: 'rejected' })}>Отклонить</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
