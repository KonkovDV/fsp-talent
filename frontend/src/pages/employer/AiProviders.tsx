import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../../api/client'

interface Kind { kind: string; label: string; params: string[]; hint: string; hosts: string[] }
interface Row {
  id: string; kind: string; kind_label: string; label: string; model: string; check_model: string | null
  params: Record<string, string>; is_active: boolean; created_at: string; activated_at: string | null
}
interface State {
  kinds: Kind[]; items: Row[]; can_edit: boolean
  in_use: { source: 'db' | 'env'; kind: string; model: string } | null
}

const PARAM_RU: Record<string, string> = { folder_id: 'ID каталога Yandex Cloud', project: 'Имя проекта MWS', scope: 'Scope GigaChat' }
const EMPTY = { kind: '', label: '', model: '', check_model: '', secret: '', params: {} as Record<string, string> }

/** Choice from a fixed list of Russian clouds. No address field: hosts are fixed on the server. */
export default function AiProviders() {
  const qc = useQueryClient()
  const { data, isError, error } = useQuery({
    queryKey: ['ai-providers'],
    queryFn: () => api.get<State>('/moderation/ai-providers').then(r => r.data),
  })
  const [form, setForm] = useState(EMPTY)
  const [note, setNote] = useState('')
  const refresh = () => qc.invalidateQueries({ queryKey: ['ai-providers'] })
  const fail = (fallback: string) => (e: unknown) => setNote(apiError(e, fallback))
  const add = useMutation({
    mutationFn: () => api.post('/moderation/ai-providers', { ...form, check_model: form.check_model || null }),
    onSuccess: () => { setForm(EMPTY); setNote('Провайдер сохранён. Ключ больше не показывается.'); refresh() },
    onError: fail('Провайдер не сохранён'),
  })
  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/moderation/ai-providers/${id}/activate`),
    onSuccess: () => { setNote('Провайдер включён. Остальные экземпляры сервера подхватят его за 30 секунд.'); refresh() },
    onError: fail('Провайдер не включён'),
  })
  const off = useMutation({
    mutationFn: () => api.post('/moderation/ai-providers/deactivate'),
    onSuccess: () => { setNote('Возврат к GigaChat из настроек сервера.'); refresh() },
    onError: fail('Не выключено'),
  })
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/moderation/ai-providers/${id}`),
    onSuccess: refresh,
    onError: fail('Провайдер не удалён'),
  })
  const check = useMutation({
    mutationFn: (id: string) => api.post<{ ok: boolean; reason: string | null }>(`/moderation/ai-providers/${id}/check`).then(r => r.data),
    onSuccess: r => setNote(r.ok ? 'Модель ответила.' : `Модель не ответила: ${r.reason ?? 'причина неизвестна'}`),
    onError: fail('Проверка не прошла'),
  })

  if (isError) return <p className="notice-error mt-8" role="alert">{apiError(error, 'Раздел провайдеров недоступен')}</p>
  if (!data) return null
  const kind = data.kinds.find(k => k.kind === form.kind)
  const inUse = data.in_use
    ? `${data.kinds.find(k => k.kind === data.in_use!.kind)?.label ?? data.in_use.kind}, модель ${data.in_use.model}${data.in_use.source === 'env' ? ' (из настроек сервера)' : ''}`
    : 'модель выключена, работают только правила'
  return (
    <section className="mt-10 space-y-4" aria-labelledby="ai-h" data-testid="ai-providers">
      <div>
        <h2 id="ai-h" className="font-display text-xl font-bold text-ink">ИИ-провайдер</h2>
        <p className="mt-1 text-sm text-ink-2">
          Только российские облака из списка. Модель ищет навыки в резюме с цитатами и пишет черновики заданий;
          кандидатов она не ранжирует. Имя, почта и телефон вырезаются до отправки.
        </p>
        <p className="mt-2 text-sm text-ink" data-testid="ai-in-use">Сейчас: {inUse}</p>
      </div>
      {data.items.length > 0 && (
        <ul className="space-y-2">
          {data.items.map(row => (
            <li key={row.id} className="card flex flex-wrap items-center gap-3" data-testid="ai-row">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink">{row.label} {row.is_active && <span className="badge-ok ml-2">включён</span>}</p>
                <p className="text-sm text-ink-2">{row.kind_label} · {row.model}{row.check_model ? ` · проверка ${row.check_model}` : ''}</p>
              </div>
              {data.can_edit && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-ghost btn-sm" disabled={check.isPending} onClick={() => check.mutate(row.id)}>Проверить</button>
                  {!row.is_active && <button type="button" className="btn-secondary btn-sm" disabled={activate.isPending} onClick={() => activate.mutate(row.id)}>Включить</button>}
                  <button type="button" className="btn-ghost btn-sm" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>Удалить</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {data.can_edit ? (
        <form className="card grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); add.mutate() }}>
          <label className="text-sm text-ink-2">Провайдер
            <select className="input mt-1 w-full" value={form.kind} onChange={e => setForm({ ...EMPTY, kind: e.target.value })}>
              <option value="">Выберите</option>
              {data.kinds.map(k => <option key={k.kind} value={k.kind}>{k.label}</option>)}
            </select>
          </label>
          <label className="text-sm text-ink-2">Название
            <input className="input mt-1 w-full" maxLength={80} value={form.label} onChange={e => setForm({ ...form, label: e.target.value })} />
          </label>
          <label className="text-sm text-ink-2">Модель
            <input className="input mt-1 w-full font-mono" maxLength={100} value={form.model} onChange={e => setForm({ ...form, model: e.target.value })} />
          </label>
          <label className="text-sm text-ink-2">Проверяющая модель (для черновиков)
            <input className="input mt-1 w-full font-mono" maxLength={100} value={form.check_model} onChange={e => setForm({ ...form, check_model: e.target.value })} />
          </label>
          {kind?.params.map(name => (
            <label key={name} className="text-sm text-ink-2">{PARAM_RU[name] ?? name}
              <input className="input mt-1 w-full font-mono" maxLength={63} value={form.params[name] ?? ''}
                onChange={e => setForm({ ...form, params: { ...form.params, [name]: e.target.value } })} />
            </label>
          ))}
          <label className="text-sm text-ink-2">Ключ
            <input className="input mt-1 w-full font-mono" type="password" autoComplete="off" maxLength={2000}
              value={form.secret} onChange={e => setForm({ ...form, secret: e.target.value })} />
          </label>
          {kind && <p className="text-xs text-ink-3 sm:col-span-2">{kind.hint}. Адрес: {kind.hosts.join(', ')}</p>}
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <button className="btn-primary" type="submit" disabled={add.isPending || !form.kind || !form.label || !form.model || !form.secret}>Сохранить</button>
            {data.items.some(r => r.is_active) && <button className="btn-ghost" type="button" disabled={off.isPending} onClick={() => off.mutate()}>Вернуть GigaChat из настроек</button>}
          </div>
        </form>
      ) : (
        <p className="text-sm text-ink-2" data-testid="ai-locked">Ключи меняются только под вторым фактором. Включите его на сервере: <code>python -m app.services.totp enroll &lt;почта&gt;</code></p>
      )}
      {note && <p className="text-sm text-ink" role="status">{note}</p>}
    </section>
  )
}
