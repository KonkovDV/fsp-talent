import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMyOffers, respondToOffer } from '../../api/client'

export default function CandidateOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading } = useQuery({
    queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data)
  })
  const mut = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'accept' | 'reject' }) =>
      respondToOffer(id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myOffers'] }),
  })
  const STATUS: Record<string, string> = {
    pending: 'ожидает', accepted: 'принят', rejected: 'отклонён', expired: 'истёк', withdrawn: 'отозван',
  }
  const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'офис' }
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Офферы</h1>
      {isLoading && <div className="animate-pulse h-40 bg-gray-100 rounded-2xl" />}
      {offers.map((o: any) => (
        <div key={o.id} className="card">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-semibold">{o.company}</p>
              <p className="text-sm text-gray-500">{o.role} · {FORMAT[o.work_format] ?? o.work_format}</p>
              <p className="text-sm text-fsp-violet font-medium mt-1 font-mono">
                {o.salary_from.toLocaleString('ru-RU')} — {o.salary_to.toLocaleString('ru-RU')} {o.currency}
              </p>
              {o.message && <p className="text-sm text-gray-600 mt-2">{o.message}</p>}
            </div>
            <span className="badge bg-gray-100 text-gray-700">{STATUS[o.status] ?? o.status}</span>
          </div>
          {o.status === 'pending' && (
            <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100">
              <button onClick={() => mut.mutate({ id: o.id, action: 'accept' })}
                className="btn-primary text-sm py-2">Принять и открыть контакты</button>
              <button onClick={() => mut.mutate({ id: o.id, action: 'reject' })}
                className="btn-secondary text-sm py-2">Отклонить</button>
            </div>
          )}
        </div>
      ))}
      {!isLoading && offers.length === 0 && (
        <div className="card text-center text-gray-400 py-12">Офферов пока нет</div>
      )}
    </div>
  )
}
