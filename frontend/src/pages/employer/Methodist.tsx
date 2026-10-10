import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError, itemPsychometrics } from '../../api/client'
import ItemDrafts from './ItemDrafts'
import { Empty, PageHeader, Skeleton } from '../../components/ui'

interface Held { item_key: string; family_id: string; level: number; z: number; n: number }

export default function Methodist() {
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const access = useQuery({
    queryKey: ['methodist'],
    queryFn: () => api.get('/methodist').then(r => r.data),
    retry: false,
  })
  const held = useQuery({
    queryKey: ['quarantine'],
    enabled: !!access.data,
    queryFn: () => api.get<Held[]>('/methodist/quarantine').then(r => r.data),
  })
  const stats = useQuery({
    queryKey: ['methodist-stats'],
    enabled: !!access.data,
    queryFn: () => itemPsychometrics('backend').then(r => r.data),
  })
  const release = useMutation({
    mutationFn: (key: string) => api.post(`/methodist/items/${encodeURIComponent(key)}/release`, { note }),
    onSuccess: () => { setError(''); setNote(''); qc.invalidateQueries({ queryKey: ['quarantine'] }) },
    onError: e => setError(apiError(e)),
  })
  if (access.isLoading) return <Skeleton className="h-40" />
  if (access.isError) return <p className="notice-error" role="alert">Раздел методиста. Роль ставится командой на сервере, в кабинете её нет.</p>

  return (
    <div>
      <PageHeader title="Методист" lead="Черновики заданий, карантин ключей и пороги. Работодатель этого не видит: в вакансии остаются только доли тем и примеры без ответов." />
      <ItemDrafts />
      <h2 className="mb-3 mt-8 font-display text-xl font-bold text-ink">Карантин</h2>
      {held.data && held.data.length === 0 && <Empty title="Карантина нет">Ключ попадает сюда, когда доля верных ответов выше модели.</Empty>}
      <ul className="space-y-2">
        {(held.data ?? []).map(row => (
          <li key={row.item_key} className="card flex flex-wrap items-center justify-between gap-3 text-sm">
            <span className="text-ink">{row.family_id}, уровень {row.level}, z {row.z}, ответов {row.n}</span>
            <button type="button" className="btn-secondary btn-sm" onClick={() => release.mutate(row.item_key)} disabled={note.trim().length < 3 || release.isPending}>Вернуть в банк</button>
          </li>
        ))}
      </ul>
      {(held.data?.length ?? 0) > 0 && (
        <label className="mt-3 block text-sm">Заметка к возврату
          <input className="input mt-1" value={note} onChange={e => setNote(e.target.value)} maxLength={500} placeholder="почему ключ можно вернуть" />
        </label>
      )}
      {error && <p className="notice-error mt-3" role="alert">{error}</p>}
      <h2 className="mb-3 mt-8 font-display text-xl font-bold text-ink">Пороги, бэкенд</h2>
      <p className="text-sm text-ink-2">{stats.data ? 'Сводка по специализации открыта только для чтения. Ответы заданий в неё не входят.' : 'Сводка загружается.'}</p>
    </div>
  )
}
