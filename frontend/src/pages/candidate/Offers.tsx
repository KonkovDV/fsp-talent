import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMyOffers, respondToOffer } from '../../api/client'
import { Empty, PageHeader, Skeleton, date, rub } from '../../components/ui'

interface Offer {
  id: string; company: string; role: string; contact_method: string | null; salary_from: number; salary_to: number
  work_format: string; message: string | null; status: string; created_at: string; expires_at: string | null
  company_profile?: { industry: string | null; website: string | null; about: string | null; inn_given: boolean }
}
const STATUS: Record<string, [string, string]> = {
  pending: ['ждёт ответа', 'badge-warn'], accepted: ['принято', 'badge-ok'], rejected: ['отклонено', 'badge-vc'],
  expired: ['срок истёк', 'badge-vc'], withdrawn: ['отозвано', 'badge-vc'],
}
const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }

export default function CandidateOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading } = useQuery<Offer[]>({ queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data) })
  const respond = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'accept' | 'reject' }) => respondToOffer(id, action),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myOffers'] }),
  })
  return (
    <div>
      <PageHeader title="Приглашения"
        lead="Работодатель пишет первым и сразу называет зарплату. Ваши имя и контакты он увидит, только если вы примете приглашение." />
      {isLoading && <Skeleton className="h-40" />}
      {!isLoading && offers.length === 0 && <Empty title="Приглашений пока нет">Подтвердите грейд тестом и заполните навыки — так вас быстрее найдут.</Empty>}
      <ul className="space-y-4">
        {offers.map(o => {
          const [label, cls] = STATUS[o.status] ?? [o.status, 'badge-vc']
          return (
            <li key={o.id} className={`card ${o.status === 'pending' ? 'ring-1 ring-inset ring-accent/40' : ''}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-4">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-accent-soft font-display text-lg font-bold text-accent" aria-hidden>{o.company.slice(0, 1)}</span>
                <div className="min-w-0">
                  <p className="text-sm text-ink-2">{o.company}{o.company_profile?.industry ? `, ${o.company_profile.industry}` : ''}</p>
                  <h2 className="mt-0.5 text-lg font-semibold text-ink">{o.role}</h2>
                  <p className="mt-1 text-sm text-ink-2">{FORMAT[o.work_format] ?? o.work_format}, получено {date(o.created_at)}
                    {o.expires_at && o.status === 'pending' ? `, ответить до ${date(o.expires_at)}` : ''}</p>
                </div>
                </div>
                <div className="text-right">
                  <p className="num font-display text-xl font-bold text-ink">{rub(o.salary_from)} – {rub(o.salary_to)}</p>
                  <p className="text-xs text-ink-3">до вычета НДФЛ</p>
                  <span className={`${cls} mt-2`}>{label}</span>
                </div>
              </div>
              {o.message && <blockquote className="mt-4 max-w-prose border-l-2 border-accent pl-3 text-sm text-ink">{o.message}</blockquote>}
              {o.company_profile?.about && (
                <details className="mt-3 max-w-prose text-sm">
                  <summary className="cursor-pointer text-accent">О компании</summary>
                  <p className="mt-2 text-ink-2">{o.company_profile.about}</p>
                  <p className="mt-1 text-xs text-ink-3">{[o.company_profile.website, o.company_profile.inn_given ? 'ИНН указан и проверен' : 'ИНН не указан'].filter(Boolean).join(', ')}</p>
                </details>
              )}
              {o.contact_method && <p className="mt-2 text-sm text-ink-2">Связь с компанией: <span className="text-ink">{o.contact_method}</span></p>}
              {o.status === 'pending' && (
                <div className="mt-5 flex flex-wrap gap-3 border-t border-line pt-4">
                  <button onClick={() => respond.mutate({ id: o.id, action: 'accept' })} disabled={respond.isPending} className="btn-primary">Принять и открыть контакты</button>
                  <button onClick={() => respond.mutate({ id: o.id, action: 'reject' })} disabled={respond.isPending} className="btn-secondary">Отклонить</button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
