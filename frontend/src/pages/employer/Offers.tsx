import { Fragment, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare } from 'lucide-react'
import { apiError, apiErrorCode, getMyEmployerOffers, getOfferContacts, offerMarket, withdrawOffer } from '../../api/client'
import InterviewSlots from '../../components/InterviewSlots'
import MessageThread from '../../components/MessageThread'
import { ROLE_RU, gradeRu } from '../../labels'
import { CategoryPlate, Empty, PageHeader, Skeleton, date, rub } from '../../components/ui'

interface Offer {
  id: string; role: string; salary_from: number; salary_to: number; work_format: string; status: string
  contacts_available: boolean; contact_method: string | null; candidate_viewed_at: string | null
  contacts_revealed_at: string | null; created_at: string
  expires_at: string | null; candidate: { role: string | null; grade: string | null; grade_source: string | null; label?: string | null } | null
  contacts_revoked_at?: string | null; unread_messages?: number
}
interface Contacts { display_name: string; email: string | null; telegram: string | null; phone: string | null; region: string | null }

const REASON_RU: Record<string, string> = {
  salary: 'зарплата', format: 'формат', stack: 'стек', not_looking: 'не ищет', other: 'другое',
}
const STATUS: Record<string, [string, string]> = {
  pending: ['ждёт ответа', 'badge-warn'], viewed: ['просмотрено', 'badge-brand'], accepted: ['принято', 'badge-ok'],
  rejected: ['отклонено', 'badge-vc'], expired: ['срок истёк', 'badge-vc'], withdrawn: ['отозвано', 'badge-vc'],
}

/** Sent invitations as a funnel: sent → viewed → accepted, with contacts after consent (TZ 2.2 п.3). */
export default function EmployerOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading } = useQuery<Offer[]>({ queryKey: ['employerOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data) })
  const market = useQuery({ queryKey: ['offerMarket'], queryFn: () => offerMarket().then(r => r.data as {
    reasons: { n: number; shares: Record<string, number> } | null
    salaries: { role: string; grade: string; p25: number; median: number; p75: number; n: number }[]
  }) })
  const [contacts, setContacts] = useState<Record<string, Contacts>>({})
  const [error, setError] = useState('')
  const reveal = useMutation({
    mutationFn: (id: string) => getOfferContacts(id).then(r => ({ id, data: r.data as Contacts })),
    onSuccess: ({ id, data }) => { setError(''); setContacts(c => ({ ...c, [id]: data })) },
    onError: e => setError(apiErrorCode(e) === 'contacts_hidden' || !apiErrorCode(e)
      ? 'Контакты откроются, когда кандидат примет приглашение.' : apiError(e)),
  })
  const [params] = useSearchParams()
  const [thread, setThread] = useState<string | null>(params.get('thread'))
  const [meeting, setMeeting] = useState<string | null>(null)
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
      {(market.data?.reasons || market.data?.salaries?.length) ? (
        <section className="panel-quiet mb-6 text-sm" aria-label="Рынок">
          <p className="text-ink-2">Обратная связь рынка. Цифры появляются, когда в ячейке не меньше пяти человек.</p>
          {market.data.reasons && (
            <p className="mt-2 text-ink">Отказы ({market.data.reasons.n}): {Object.entries(market.data.reasons.shares).map(([k, v]) => `${REASON_RU[k] ?? k} ${Math.round(v * 100)} %`).join(', ')}</p>
          )}
          {!!market.data.salaries.length && (
            <ul className="mt-2 space-y-1">
              {market.data.salaries.map(row => (
                <li key={`${row.role}-${row.grade}`}>{ROLE_RU[row.role] ?? row.role}, {gradeRu(row.grade)}: {rub(row.p25)} – {rub(row.median)} – {rub(row.p75)}, {row.n} чел.</li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
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
            <thead><tr><th>Кандидат</th><th>Должность</th><th className="text-right">До вычета НДФЛ</th><th>Отправлено</th><th>Статус</th><th /></tr></thead>
            <tbody>
              {offers.map(o => {
                const [label, cls] = STATUS[stage(o)] ?? [o.status, 'badge-vc']
                const c = contacts[o.id]
                return (
                  <Fragment key={o.id}>
                  <tr data-offer-id={o.id}>
                    <td>{o.candidate?.role ? <CategoryPlate role={o.candidate.role} grade={o.candidate.grade ?? ''} source={o.candidate.grade_source ?? ''} /> : (o.candidate?.label ?? '—')}
                      {c && <div className="mt-2 text-sm text-ink"><b>{c.display_name}</b><br />{[c.email, c.telegram, c.phone].filter(Boolean).join(', ')}</div>}</td>
                    <td className="text-ink">{o.role}</td>
                    <td className="num whitespace-nowrap text-right text-ink">{rub(o.salary_from)} – {rub(o.salary_to)}</td>
                    <td className="num text-ink-2">{date(o.created_at)}</td>
                    <td><span className={cls}>{label}</span>
                      {o.contacts_revoked_at && <span className="badge-vc mt-1 block w-max">контакты закрыты кандидатом</span>}</td>
                    <td className="whitespace-nowrap text-right">
                      {o.contacts_available && !c && <button onClick={() => reveal.mutate(o.id)} className="btn-secondary btn-sm">Открыть контакты</button>}
                      {o.status === 'accepted' && (
                        <button onClick={() => setMeeting(meeting === o.id ? null : o.id)} aria-expanded={meeting === o.id} className="btn-ghost btn-sm">Собеседование</button>
                      )}
                      {o.status === 'accepted' && (
                        <button onClick={() => setThread(thread === o.id ? null : o.id)} aria-expanded={thread === o.id} className="btn-ghost btn-sm">
                          <MessageSquare size={14} aria-hidden /> Переписка
                          {(o.unread_messages ?? 0) > 0 && <span className="ml-1 rounded-full bg-invite px-1.5 text-2xs text-invite-ink num" aria-label={`непрочитанных: ${o.unread_messages}`}>{o.unread_messages}</span>}
                        </button>
                      )}
                      {o.status === 'pending' && <button onClick={() => withdraw.mutate(o.id)} className="btn-ghost btn-sm">Отозвать</button>}
                    </td>
                  </tr>
                  {meeting === o.id && (
                    <tr><td colSpan={6} className="!whitespace-normal"><InterviewSlots offerId={o.id} side="employer" listKey="employerOffers" /></td></tr>
                  )}
                  {thread === o.id && (
                    <tr><td colSpan={6} className="!whitespace-normal"><MessageThread offerId={o.id} listKey="employerOffers" other="Кандидат" /></td></tr>
                  )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
