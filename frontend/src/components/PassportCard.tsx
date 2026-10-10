import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, getMyPassport, issueMyPassport, revokeMyCredential } from '../api/client'
import QrCode from './QrCode'

/** A signed link the candidate hands out at a fair or in a chat. It carries no name and no contacts. */
export default function PassportCard() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['passport'], queryFn: () => getMyPassport().then(r => r.data) })
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const issue = useMutation({
    mutationFn: () => issueMyPassport().then(r => r.data),
    onSuccess: next => { qc.setQueryData(['passport'], next); setError('') },
    onError: (e: unknown) => setError(apiError(e, 'Паспорт не выпущен')),
  })
  const revoke = useMutation({
    mutationFn: (id: string) => revokeMyCredential(id),
    onSuccess: () => { qc.setQueryData(['passport'], null); setError('') },
    onError: (e: unknown) => setError(apiError(e, 'Паспорт не отозван')),
  })
  if (isLoading) return null
  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="card space-y-3" aria-labelledby="passport-h" data-testid="passport-card">
      <div>
        <h2 id="passport-h" className="section-title">Паспорт навыков</h2>
        <p className="mt-1 text-sm text-ink-2">
          Подписанная карточка: грейды и навыки, подтверждённые тестом, и результаты ФСП без названий соревнований.
          Имени и контактов в ней нет. Новый паспорт отзывает прежнюю ссылку.
        </p>
      </div>
      {data ? (
        <div className="space-y-3">
          <QrCode value={data.url} label="QR-код ссылки на паспорт навыков" />
          <a href={data.url} className="link block break-all text-sm" data-testid="passport-link">{data.url}</a>
          <div className="flex flex-wrap gap-2">
            <button className="btn-ghost btn-sm" type="button" onClick={() => copy(data.url)}>{copied ? 'Скопировано' : 'Копировать ссылку'}</button>
            <button className="btn-ghost btn-sm" type="button" disabled={issue.isPending} onClick={() => issue.mutate()}>Обновить</button>
            <button className="btn-ghost btn-sm" type="button" disabled={revoke.isPending} onClick={() => revoke.mutate(data.id)}>Отозвать</button>
          </div>
        </div>
      ) : (
        <button className="btn-primary" type="button" disabled={issue.isPending} onClick={() => issue.mutate()}
          data-testid="passport-issue">Выпустить паспорт</button>
      )}
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
    </section>
  )
}
