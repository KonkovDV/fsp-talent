import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../../api/client'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'
import ItemDrafts from './ItemDrafts'

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

export default function Moderation() {
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
      <ItemDrafts />
    </div>
  )
}
