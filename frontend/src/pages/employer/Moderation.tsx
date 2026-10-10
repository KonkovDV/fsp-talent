import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../../api/client'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'
import AiProviders from './AiProviders'

interface Row {
  id: string
  reason: string
  vacancy_id: string | null
  offer_id: string | null
  created_at: string
}

const LABEL: Record<string, string> = {
  fake: 'фиктивная вакансия',
  salary: 'вилка не та',
  discrimination: 'оскорбление',
  spam: 'сбор данных',
  other: 'другое',
}

interface Factor { enrolled: boolean; unlocked: boolean; unlocked_until: string | null }

export default function Moderation() {
  const qc = useQueryClient()
  const [code, setCode] = useState('')
  const factor = useQuery({
    queryKey: ['moderation-totp'],
    queryFn: () => api.get<Factor>('/moderation/totp').then(r => r.data),
  })
  const unlock = useMutation({
    mutationFn: (value: string) => api.post<Factor>('/moderation/totp', { code: value }).then(r => r.data),
    onSuccess: next => { setCode(''); qc.setQueryData(['moderation-totp'], next) },
  })
  if (factor.isLoading) return <Skeleton className="h-40" />
  if (factor.isError) return <p className="notice-error" role="alert">{apiError(factor.error, 'Раздел недоступен')}</p>
  if (factor.data?.enrolled && !factor.data.unlocked) {
    return (
      <div>
        <PageHeader title="Модерация" lead="Стол защищён вторым фактором. Введите код из приложения-аутентификатора, стол откроется на 15 минут." />
        <form className="card max-w-sm space-y-3" onSubmit={e => { e.preventDefault(); unlock.mutate(code) }} data-testid="totp-form">
          <label className="block text-sm text-ink-2" htmlFor="totp-code">Код из приложения</label>
          <input id="totp-code" className="input w-full font-mono" inputMode="numeric" autoComplete="one-time-code"
            maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
          <button className="btn-primary" type="submit" disabled={unlock.isPending || code.length !== 6}>Открыть стол</button>
          {unlock.isError && <p className="notice-error" role="alert">{apiError(unlock.error, 'Код не подошёл')}</p>}
        </form>
      </div>
    )
  }
  return <Desk />
}

function SalaryFlags() {
  const flags = useQuery({
    queryKey: ['salary-flags'],
    queryFn: () => api.get<{ id: string; flag: string; company: string; role: string; salary_from: number; salary_to: number }[]>('/moderation/salary-flags').then(r => r.data),
  })
  if (!flags.data?.length) return null
  return (
    <div className="mt-8">
      <h2 className="mb-3 font-display text-xl font-bold text-ink">Вилки вне рынка</h2>
      <ul className="space-y-3">
        {flags.data.map(row => (
          <li key={row.id} className="card text-sm text-ink">
            {row.company}, {row.role}: {row.salary_from.toLocaleString('ru-RU')}–{row.salary_to.toLocaleString('ru-RU')} ₽.{' '}
            {row.flag === 'suspicious' ? 'В несколько раз выше медианы категории.' : 'Ниже половины медианы категории.'}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Desk() {
  const qc = useQueryClient()
  const list = useQuery({
    queryKey: ['moderation'],
    queryFn: () => api.get<Row[]>('/moderation/complaints').then(r => r.data),
  })
  const close = useMutation({
    mutationFn: (id: string) => api.post(`/moderation/vacancies/${id}/close`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['moderation'] }),
  })
  return (
    <div>
      <PageHeader title="Модерация" lead="Демо-стол: жалобы на вакансии и черновики заданий. Закрытие вакансии не банит человека и не прячет банк кандидатов." />
      <h2 className="mb-3 font-display text-xl font-bold text-ink">Жалобы</h2>
      {list.isLoading && <Skeleton className="h-40" />}
      {list.isError && <p className="notice-error" role="alert">{apiError(list.error, 'Список недоступен')}</p>}
      {list.data && list.data.length === 0 && <Empty title="Жалоб нет">Когда кандидат пожалуется на вакансию, строка появится здесь.</Empty>}
      {list.data && list.data.length > 0 && (
        <ul className="space-y-3">
          {list.data.map(row => (
            <li key={row.id} className="card space-y-2">
              <p className="font-medium text-ink">{LABEL[row.reason] ?? row.reason}</p>
              <p className="text-sm text-ink-2">{date(row.created_at)}</p>
              {row.vacancy_id && (
                <button type="button" className="btn-secondary btn-sm" disabled={close.isPending}
                  onClick={() => close.mutate(row.vacancy_id!)}>Закрыть вакансию</button>
              )}
            </li>
          ))}
        </ul>
      )}
      <SalaryFlags />
      <AiProviders />
    </div>
  )
}
