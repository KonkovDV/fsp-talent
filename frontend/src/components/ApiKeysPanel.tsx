import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../api/client'

export interface ApiKeyRow { id: string; prefix: string; label: string | null; created_at: string; last_used_at: string | null; revoked_at: string | null }

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '—')

/** Examples the company copies into its ATS. The key goes in a header, never in the address. */
export function exportExamples(origin: string, key: string) {
  const url = `${origin}/api/v1/employer/integrations/export`
  return {
    json: `curl -H "X-API-Key: ${key}" "${url}?fmt=json"`,
    csv: `curl -H "X-API-Key: ${key}" "${url}?fmt=csv" -o candidates.csv`,
  }
}

function Copy({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false)
  return (
    <button type="button" className="btn-ghost btn-sm" aria-label={label}
      onClick={() => { void navigator.clipboard?.writeText(text); setDone(true) }}>
      {done ? 'Скопировано' : 'Копировать'}
    </button>
  )
}

/** Read-only API keys: create (shown once), list by prefix, revoke. */
export default function ApiKeysPanel() {
  const qc = useQueryClient()
  const [label, setLabel] = useState('')
  const [fresh, setFresh] = useState('')
  const [error, setError] = useState('')
  const keys = useQuery({ queryKey: ['apiKeys'], queryFn: () => api.get<ApiKeyRow[]>('/employer/integrations/keys').then(r => r.data) })
  const create = useMutation({
    mutationFn: () => api.post<ApiKeyRow & { key: string }>('/employer/integrations/keys', { label: label.trim() || null }).then(r => r.data),
    onSuccess: data => { setFresh(data.key); setLabel(''); setError(''); qc.invalidateQueries({ queryKey: ['apiKeys'] }) },
    onError: e => setError(apiError(e)),
  })
  const revoke = useMutation({
    mutationFn: (id: string) => api.delete(`/employer/integrations/keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['apiKeys'] }),
    onError: e => setError(apiError(e)),
  })
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const examples = exportExamples(origin, fresh || 'fspk_…')

  return (
    <section className="card mt-6 space-y-3" aria-labelledby="api-keys-h">
      <h2 id="api-keys-h" className="font-display text-xl font-bold text-ink">API-ключи</h2>
      <p className="text-sm text-ink-2">
        Ключ только читает выгрузку согласившихся кандидатов вашей компании (JSON или CSV). Мы храним лишь его хеш SHA-256,
        поэтому полный ключ показывается один раз. Активных ключей — не больше трёх.
      </p>
      <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); create.mutate() }}>
        <label className="sr-only" htmlFor="key-label">Название ключа</label>
        <input id="key-label" className="input max-w-xs" maxLength={80} value={label} onChange={e => setLabel(e.target.value)} placeholder="Например, ATS отдела найма" />
        <button className="btn-primary btn-sm" disabled={create.isPending}>Создать ключ</button>
      </form>
      {fresh && (
        <div className="notice-ok space-y-1" role="status" data-testid="api-key-once">
          <p>Ключ показывается один раз, сохраните его:</p>
          <p className="flex flex-wrap items-center gap-2"><code className="break-all font-mono text-xs">{fresh}</code><Copy text={fresh} label="Копировать ключ" /></p>
        </div>
      )}
      {error && <p className="notice-error" role="alert">{error}</p>}
      <ul className="space-y-2">
        {(keys.data ?? []).map(row => (
          <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3 text-sm" data-testid="api-key-row">
            <span className="min-w-0">
              <code className="font-mono text-xs">{row.prefix}</code>{row.label ? ` · ${row.label}` : ''}
              <span className="block text-xs text-ink-3">создан {day(row.created_at)}, использован {day(row.last_used_at)}{row.revoked_at ? `, отозван ${day(row.revoked_at)}` : ''}</span>
            </span>
            {!row.revoked_at && <button type="button" className="btn-ghost btn-sm" onClick={() => revoke.mutate(row.id)}>Отозвать</button>}
          </li>
        ))}
      </ul>
      <div className="space-y-2">
        <p className="text-sm font-medium text-ink">Пример запроса</p>
        {(['json', 'csv'] as const).map(kind => (
          <p key={kind} className="flex flex-wrap items-center gap-2">
            <code className="break-all rounded bg-sunken px-2 py-1 font-mono text-xs" data-testid={`example-${kind}`}>{examples[kind]}</code>
            <Copy text={examples[kind]} label={`Копировать пример ${kind.toUpperCase()}`} />
          </p>
        ))}
        <p className="text-xs text-ink-3">Схема ответа — в <a className="underline" href="/docs" target="_blank" rel="noopener">API (Swagger)</a>. События о согласии приходят вебхуками выше.</p>
      </div>
    </section>
  )
}
