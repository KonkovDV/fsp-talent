import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MessageSquare } from 'lucide-react'
import { apiError, fileComplaint, getMyOffers, respondToOffer, revokeContacts, updateMyProfile } from '../../api/client'
import InterviewSlots from '../../components/InterviewSlots'
import MessageThread from '../../components/MessageThread'
import { Empty, PageHeader, Skeleton, date, rub } from '../../components/ui'
import { netLine } from '../../money'

interface Offer {
  id: string; company: string; role: string; contact_method: string | null; salary_from: number; salary_to: number
  market_flag?: string | null
  work_format: string; message: string | null; status: string; created_at: string; expires_at: string | null
  company_profile?: { industry: string | null; website: string | null; about: string | null; inn_given: boolean
    rating?: { score: number; label: string; demo: boolean; note: string } }
  contacts_revoked_at?: string | null; unread_messages?: number
}
const STATUS: Record<string, [string, string]> = {
  pending: ['ждёт ответа', 'badge-warn'], accepted: ['принято', 'badge-ok'], rejected: ['отклонено', 'badge-vc'],
  expired: ['срок истёк', 'badge-vc'], withdrawn: ['отозвано', 'badge-vc'],
}
const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }
const REASONS: [string, string][] = [
  ['', 'Выберите причину'],
  ['salary', 'Зарплата'],
  ['format', 'Формат работы'],
  ['stack', 'Стек'],
  ['not_looking', 'Сейчас не ищу'],
  ['other', 'Другое'],
]
const COMPLAINTS: [string, string][] = [
  ['не_вакансия', 'Это не вакансия'],
  ['сбор_данных', 'Собирают данные'],
  ['зарплата_не_та', 'Зарплата не та'],
  ['оскорбление', 'Оскорбление'],
  ['другое', 'Другое'],
]

export default function CandidateOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading, isError, error } = useQuery<Offer[]>({ queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data) })
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [hideFor, setHideFor] = useState<string | null>(null)
  const [hidden, setHidden] = useState(false)
  const [hideError, setHideError] = useState('')
  const respond = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'accept' | 'reject' }) =>
      respondToOffer(id, action, action === 'reject' ? reasons[id] : undefined),
    onSuccess: (res, vars) => {
      setRespondError('')
      qc.invalidateQueries({ queryKey: ['myOffers'] })
      if (vars.action === 'accept' && res.data?.suggest_hide) setHideFor(vars.id)
    },
    onError: e => setRespondError(apiError(e, 'Ответ не отправлен')),
  })
  const hideMe = useMutation({
    mutationFn: () => updateMyProfile({ job_search: 'not_looking' }),
    onSuccess: () => { setHideFor(null); setHidden(true); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: e => setHideError(apiError(e, 'Не удалось скрыть карточку')),
  })
  const [params, setParams] = useSearchParams()
  const thread = params.get('thread')
  const toggleThread = (id: string) => {
    const next = new URLSearchParams(params)
    if (thread === id) next.delete('thread')
    else next.set('thread', id)
    setParams(next, { replace: true })
  }
  const [confirm, setConfirm] = useState<string | null>(null)
  const [complaintFor, setComplaintFor] = useState<string | null>(null)
  const [complaintReason, setComplaintReason] = useState('не_вакансия')
  const [complaintNote, setComplaintNote] = useState('')
  const [revokeError, setRevokeError] = useState('')
  const [respondError, setRespondError] = useState('')
  const complain = useMutation({
    mutationFn: (id: string) => fileComplaint(id, complaintReason),
    onSuccess: (res) => {
      setComplaintNote(res.data.paused
        ? 'Жалоба принята. Приглашения этой компании приостановлены до проверки.'
        : 'Жалоба принята.')
      setComplaintFor(null)
    },
    onError: e => setComplaintNote(apiError(e, 'Не удалось отправить жалобу')),
  })
  const revoke = useMutation({
    mutationFn: (id: string) => revokeContacts(id),
    onSuccess: () => { setConfirm(null); setRevokeError(''); qc.invalidateQueries({ queryKey: ['myOffers'] }) },
    onError: e => setRevokeError(apiError(e, 'Не удалось закрыть контакты')),
  })
  return (
    <div>
      <PageHeader title="Приглашения"
        lead="Работодатель пишет первым и сразу называет зарплату. Ваши имя и контакты он увидит, только если вы примете приглашение." />
      {isLoading && <Skeleton className="h-40" />}
      {isError && <p className="notice-error mb-4" role="alert">{apiError(error, 'Не удалось загрузить приглашения')}</p>}
      {complaintNote && <p className="notice-info mb-4" role="status">{complaintNote}</p>}
      {!isLoading && !isError && offers.length === 0 && <Empty title="Приглашений пока нет">Подтвердите грейд тестом и заполните навыки — так вас быстрее найдут.</Empty>}
      {respondError && <p className="notice-error mb-4" role="alert">{respondError}</p>}
      {!isError && offers.length === 50 && <p className="mb-4 text-sm text-ink-2">Показаны последние 50 приглашений. Ждущие ответа стоят в начале списка.</p>}
      <ul className="space-y-4">
        {offers.map(o => {
          const [label, cls] = STATUS[o.status] ?? [o.status, 'badge-vc']
          return (
            <li key={o.id} className={`card relative overflow-hidden ${o.status === 'pending' ? 'border-invite/40 dark:border-invite/40' : ''}`}>
              {o.status === 'pending' && <span className="absolute inset-y-0 left-0 w-1 bg-invite" aria-hidden />}
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-4">
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-accent-soft font-display text-lg font-bold text-accent" aria-hidden>{o.company.slice(0, 1)}</span>
                <div className="min-w-0">
                  <p className="text-sm text-ink-2">{o.company}{o.company_profile?.industry ? `, ${o.company_profile.industry}` : ''}</p>
                  {o.company_profile?.rating && (
                    <p className="mt-1 text-xs text-ink-2">Балл компании {o.company_profile.rating.score} из 10, {o.company_profile.rating.label}. {o.company_profile.rating.note}</p>
                  )}
                  <h2 className="mt-0.5 font-display text-lg font-bold tracking-[-0.01em] text-ink">{o.role}</h2>
                  <p className="mt-1 text-sm text-ink-2">{FORMAT[o.work_format] ?? o.work_format}, получено {date(o.created_at)}
                    {o.expires_at && o.status === 'pending' ? `, ответить до ${date(o.expires_at)}` : ''}</p>
                </div>
                </div>
                <div className="sm:text-right">
                  <p className="num font-display text-xl font-bold text-ink">{rub(o.salary_from)} – {rub(o.salary_to)}</p>
                  <p className="text-xs text-ink-3">до вычета НДФЛ</p>
                  <p className="text-xs text-ink-3">{netLine(o.salary_from, o.salary_to)}</p>
                  {o.market_flag === 'below_market' && <p className="text-xs text-warn">вилка ниже рынка категории</p>}
                  <span className={`${cls} mt-2`}>{label}</span>
                </div>
              </div>
              {o.message && <blockquote className="mt-4 max-w-prose border-l-2 border-accent pl-3 text-sm text-ink">{o.message}</blockquote>}
              {o.company_profile?.about && (
                <details className="mt-3 max-w-prose text-sm">
                  <summary className="inline-flex min-h-6 cursor-pointer items-center font-medium text-accent">О компании</summary>
                  <p className="mt-2 text-ink-2">{o.company_profile.about}</p>
                  <p className="mt-1 text-xs text-ink-3">{[o.company_profile.website, o.company_profile.inn_given ? 'ИНН указан и проверен' : 'ИНН не указан'].filter(Boolean).join(', ')}</p>
                </details>
              )}
              {o.contact_method && <p className="mt-2 text-sm text-ink-2">Связь с компанией: <span className="text-ink">{o.contact_method}</span></p>}
              {complaintFor !== o.id ? (
                <button type="button" className="btn-ghost btn-sm mt-3" onClick={() => { setComplaintFor(o.id); setComplaintNote('') }}>Пожаловаться</button>
              ) : (
                <form className="mt-3 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center" onSubmit={e => { e.preventDefault(); complain.mutate(o.id) }}>
                  <label className="text-sm text-ink-2">Причина
                    <select value={complaintReason} onChange={e => setComplaintReason(e.target.value)} className="select mt-1 sm:ml-2 sm:mt-0" aria-label="Причина жалобы">
                      {COMPLAINTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                  </label>
                  <button type="submit" className="btn-secondary btn-sm" disabled={complain.isPending}>Отправить жалобу</button>
                </form>
              )}
              {o.status === 'accepted' && (
                <div className="mt-5 border-t border-line pt-4">
                  {o.contacts_revoked_at
                    ? <p className="text-sm text-ink-2">Контакты для этой компании закрыты {date(o.contacts_revoked_at)}. Другие компании это не затрагивает.</p>
                    : <p className="text-sm text-ink-2">Компании открыты ваши контакты.</p>}
                  {hidden && <p className="mt-2 text-sm text-ink-2">Карточка скрыта из поиска. Вернуть её можно в профиле.</p>}
                  {hideFor === o.id && (
                    <div className="notice-info mt-3 flex-col">
                      <p>Приглашение принято. Скрыть карточку из поиска, пока вы не ищете работу? Согласие на публикацию остаётся.</p>
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => hideMe.mutate()} disabled={hideMe.isPending} className="btn-primary btn-sm">Да, скрыть меня</button>
                        <button type="button" onClick={() => setHideFor(null)} className="btn-secondary btn-sm">Не сейчас</button>
                      </div>
                      {hideError && <p className="notice-error" role="alert">{hideError}</p>}
                    </div>
                  )}
                  <InterviewSlots offerId={o.id} side="participant" listKey="myOffers" />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => toggleThread(o.id)} aria-expanded={thread === o.id} className="btn-secondary btn-sm">
                      <MessageSquare size={14} aria-hidden /> Переписка
                      {(o.unread_messages ?? 0) > 0 && <span className="count ml-1" aria-label={`непрочитанных: ${o.unread_messages}`}>{o.unread_messages}</span>}
                    </button>
                    {!o.contacts_revoked_at && confirm !== o.id && (
                      <button onClick={() => setConfirm(o.id)} className="btn-ghost btn-sm">Закрыть контакты для этой компании</button>
                    )}
                  </div>
                  {confirm === o.id && (
                    <div className="notice-info mt-3 flex-col" role="alertdialog" aria-labelledby={`rv-${o.id}`}>
                      <p id={`rv-${o.id}`}>«{o.company}» больше не сможет открыть ваши имя, email, Telegram и телефон, а переписка станет только для чтения.
                        Согласие на обработку данных для других компаний остаётся.</p>
                      <div className="flex flex-wrap gap-2">
                        <button onClick={() => revoke.mutate(o.id)} disabled={revoke.isPending} className="btn-primary btn-sm">Закрыть контакты</button>
                        <button onClick={() => setConfirm(null)} className="btn-secondary btn-sm">Отмена</button>
                      </div>
                    </div>
                  )}
                  {revokeError && confirm === o.id && <p className="notice-error mt-3" role="alert">{revokeError}</p>}
                  {thread === o.id && <MessageThread offerId={o.id} listKey="myOffers" other={o.company} />}
                </div>
              )}
              {o.status === 'pending' && (
                <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
                  <button onClick={() => respond.mutate({ id: o.id, action: 'accept' })} disabled={respond.isPending} className="btn-primary">Принять и открыть контакты</button>
                  <label className="text-sm text-ink-2">Причина отказа
                    <select value={reasons[o.id] ?? ''} onChange={e => setReasons(prev => ({ ...prev, [o.id]: e.target.value }))} className="select ml-2" aria-label="Причина отказа">
                      {REASONS.map(([value, label]) => <option key={value || 'none'} value={value} disabled={value === ''}>{label}</option>)}
                    </select>
                  </label>
                  <button onClick={() => respond.mutate({ id: o.id, action: 'reject' })} disabled={respond.isPending || !reasons[o.id]} className="btn-secondary">Отклонить</button>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
