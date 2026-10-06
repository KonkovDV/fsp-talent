import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMyEmployerOffers, getOfferContacts, withdrawOffer } from '../../api/client'
import { CategoryPlate, Empty, PageHeader, Skeleton, date, rub } from '../../components/ui'

interface Offer {
  id: string; role: string; salary_from: number; salary_to: number; work_format: string; status: string
  contacts_available: boolean; contact_method: string | null; candidate_viewed_at: string | null
  contacts_revealed_at: string | null; created_at: string
  expires_at: string | null; candidate: { role: string; grade: string; grade_source: string } | null
}
interface Contacts { display_name: string; email: string | null; telegram: string | null; phone: string | null; region: string | null }

const STATUS: Record<string, [string, string]> = {
  pending: ['ждёт ответа', 'badge-warn'], viewed: ['просмотрено', 'badge-brand'], accepted: ['принято', 'badge-ok'],
  rejected: ['отклонено', 'badge-vc'], expired: ['срок истёк', 'badge-vc'], withdrawn: ['отозвано', 'badge-vc'],
}

/** Sent invitations as a funnel: sent → viewed → accepted, with contacts after consent (TZ 2.2 п.3). */
export default function EmployerOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading } = useQuery<Offer[]>({ queryKey: ['employerOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data) })
  const [contacts, setContacts] = useState<Record<string, Contacts>>({})
  const [error, setError] = useState('')
  const reveal = useMutation({
    mutationFn: (id: string) => getOfferContacts(id).then(r => ({ id, data: r.data as Contacts })),
    onSuccess: ({ id, data }) => { setError(''); setContacts(c => ({ ...c, [id]: data })) },
    onError: () => setError('Контакты откроются, когда кандидат примет приглашение.'),
  })
  const withdraw = useMutation({ mutationFn: withdrawOffer, onSuccess: () => qc.invalidateQueries({ queryKey: ['employerOffers'] }) })

  const stage = (o: Offer) => (o.status === 'pending' && o.candidate_viewed_at ? 'viewed' : o.status)
  const funnel = [
    ['Отправлено', offers.length],
    ['Просмотрено', offers.filter(o => o.candidate_viewed_at).length],
    ['Принято', offers.filter(o => o.status === 'accepted').length],
    ['Контакты открыты', offers.filter(o => o.contacts_revealed_at).length],
  ] as const

  return (
    <div>
      <PageHeader title="Приглашения" lead="Статус каждого приглашения. Контакты открываются после согласия кандидата, каждое открытие записывается в журнал." />
      {offers.length > 0 && (
        <dl className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {funnel.map(([label, n]) => (
            <div key={label} className="stat-card"><dt className="stat-card-label">{label}</dt><dd className="stat-card-value">{n}</dd></div>
          ))}
        </dl>
      )}
      {error && <p className="notice-error mb-4" role="alert">{error}</p>}
      {isLoading && <Skeleton className="h-48" />}
      {!isLoading && offers.length === 0 && <Empty title="Вы ещё никого не пригласили">Найдите кандидата в поиске или в подборке по потребности и нажмите «Пригласить».</Empty>}
      {offers.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="protocol">
            <thead><tr><th>Кандидат</th><th>Должность</th><th className="text-right">Зарплата</th><th>Отправлено</th><th>Статус</th><th /></tr></thead>
            <tbody>
              {offers.map(o => {
                const [label, cls] = STATUS[stage(o)] ?? [o.status, 'badge-vc']
                const c = contacts[o.id]
                return (
                  <tr key={o.id}>
                    <td>{o.candidate ? <CategoryPlate role={o.candidate.role} grade={o.candidate.grade} source={o.candidate.grade_source} /> : '—'}
                      {c && <div className="mt-2 text-sm text-ink"><b>{c.display_name}</b><br />{[c.email, c.telegram, c.phone].filter(Boolean).join(', ')}</div>}</td>
                    <td className="text-ink">{o.role}</td>
                    <td className="num whitespace-nowrap text-right text-ink">{rub(o.salary_from)} – {rub(o.salary_to)}</td>
                    <td className="num text-ink-2">{date(o.created_at)}</td>
                    <td><span className={cls}>{label}</span></td>
                    <td className="whitespace-nowrap text-right">
                      {o.contacts_available && !c && <button onClick={() => reveal.mutate(o.id)} className="btn-secondary btn-sm">Открыть контакты</button>}
                      {o.status === 'pending' && <button onClick={() => withdraw.mutate(o.id)} className="btn-ghost btn-sm">Отозвать</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
