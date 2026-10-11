import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../../api/client'
import { Empty, PageHeader } from '../../components/ui'

interface Endpoint { id: string; url: string; active: boolean }
interface Delivery { id: string; event_type: string; status: string; attempt: number; last_code: number | null; last_error: string | null }

const STATUS: Record<string, string> = { pending: 'ждёт', delivered: 'доставлено', dead: 'сдались' }

export default function Integrations() {
  const qc = useQueryClient()
  const [url, setUrl] = useState('')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState('')
  const endpoints = useQuery({ queryKey: ['integrations'], queryFn: () => api.get<Endpoint[]>('/employer/integrations').then(r => r.data) })
  const log = useQuery({ queryKey: ['deliveries'], queryFn: () => api.get<Delivery[]>('/employer/integrations/deliveries').then(r => r.data) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['integrations'] }); qc.invalidateQueries({ queryKey: ['deliveries'] }) }
  const create = useMutation({
    mutationFn: (body: { url?: string; use_sandbox?: boolean }) => api.post('/employer/integrations', body).then(r => r.data as { secret: string }),
    onSuccess: data => { setSecret(data.secret); setError(''); setUrl(''); refresh() },
    onError: e => setError(apiError(e)),
  })
  const test = useMutation({
    mutationFn: () => api.post('/employer/integrations/test'),
    onSuccess: () => { setError(''); refresh() },
    onError: e => setError(apiError(e)),
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/employer/integrations/${id}`),
    onSuccess: refresh,
  })

  return (
    <div>
      <PageHeader title="Интеграции" lead="События уходят в вашу ATS (систему учёта кандидатов) после согласия кандидата. Подпись по стандарту Standard Webhooks (подпись событий), повтор доставки, чужой адрес только по https." />
      <form className="card space-y-3" onSubmit={e => { e.preventDefault(); create.mutate({ url }) }}>
        <label className="field-label" htmlFor="ats-url">Адрес приёмника</label>
        <input id="ats-url" className="input" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://ats.example.ru/hooks/fsp" />
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary btn-sm" disabled={create.isPending || url.trim().length < 8}>Подключить</button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => create.mutate({ use_sandbox: true })}>Приёмник стенда</button>
          <button type="button" className="btn-secondary btn-sm" onClick={() => test.mutate()} disabled={test.isPending}>Тестовое событие</button>
          <a className="btn-ghost btn-sm" href="/api/v1/employer/integrations/export?format=csv">Скачать CSV</a>
        </div>
        {secret && <p className="notice-ok" role="status">Секрет показывается один раз: {secret}</p>}
        {error && <p className="notice-error" role="alert">{error}</p>}
      </form>
      <ul className="mt-4 space-y-2">
        {(endpoints.data ?? []).map(row => (
          <li key={row.id} className="card flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 break-all text-ink">{row.url}</span>
            <button type="button" className="btn-ghost btn-sm" onClick={() => remove.mutate(row.id)}>Удалить</button>
          </li>
        ))}
      </ul>
      <h2 className="mb-3 mt-8 font-display text-xl font-bold text-ink">Доставка</h2>
      {log.data && log.data.length === 0 && <Empty title="Событий ещё нет">Подключите адрес и отправьте тестовое событие.</Empty>}
      <ul className="space-y-2">
        {(log.data ?? []).map(row => (
          <li key={row.id} className="card text-sm text-ink">
            {row.event_type}: {STATUS[row.status] ?? row.status}
            {row.last_code ? `, ответ ${row.last_code}` : ''}{row.last_error ? `, ${row.last_error}` : ''}, попытка {row.attempt}
          </li>
        ))}
      </ul>
    </div>
  )
}
