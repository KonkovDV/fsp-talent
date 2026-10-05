import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Check, Circle } from 'lucide-react'
import { getMyOffers, getMyProfile } from '../../api/client'
import SurveyCard from '../../components/SurveyCard'
import { CategoryPlate, Empty, Meter, PageHeader, RankBadge, SOURCE_LABEL, Skeleton, rub } from '../../components/ui'

interface Disc { discipline: string; label: string; score?: number; lcb: number; confidence: number; best_rank: string | null; events_count: number }
interface Offer { id: string; company: string; role: string; salary_from: number; salary_to: number; status: string }

/** Candidate home: the category employers see, what is missing for it, and fresh invitations. */
export default function CandidateDashboard() {
  const { data: p, isLoading } = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const { data: offers = [] } = useQuery<Offer[]>({ queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data) })

  if (isLoading || !p) return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-48" /><Skeleton className="h-64" /></div>

  const pending = offers.filter(o => o.status === 'pending')
  const steps = [
    { done: p.email_verified, text: 'Email подтверждён', to: null },
    { done: p.survey_done, text: 'Опрос: специализация и отрасль', to: '/candidate/profile' },
    { done: p.grade_source === 'assessed', text: 'Грейд подтверждён тестом', to: '/candidate/assessment' },
    { done: p.has_fsp, text: 'ФСП ID привязан (необязательно)', to: '/candidate/profile' },
    { done: p.discoverable, text: 'Карточка видна работодателям', to: '/candidate/profile' },
  ]
  const disciplines: Disc[] = p.discipline_scores ?? []

  return (
    <div className="space-y-8">
      <PageHeader title={p.display_name ? `Здравствуйте, ${p.display_name.split(' ')[0]}` : 'Кабинет'}
        lead="Так вас видит работодатель в поиске: без имени и контактов, по категории и подтверждениям." />

      {!p.survey_done && <SurveyCard profile={p} />}

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]" aria-label="Категория">
        <div className="card">
          <p className="text-xs text-ink-3">Ваша категория</p>
          <div className="mt-3"><CategoryPlate role={p.primary_role} grade={p.grade} source={p.grade_source} size="lg" /></div>
          <p className="mt-3 text-sm text-ink-2">Грейд: {SOURCE_LABEL[p.grade_source] ?? '—'}.
            {p.grade_source !== 'assessed' && ' Подтверждённый тестом грейд стоит в выдаче выше заявленного.'}</p>
          {(p.stack ?? []).length > 0 && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {(p.skills ?? []).slice(0, 14).map((s: { name: string; trust_level: string }) => (
                <span key={s.name} className={s.trust_level === 'test_confirmed' ? 'chip-active' : 'chip-default'}
                  title={s.trust_level === 'test_confirmed' ? 'Подтверждён тестом' : 'Заявлен'}>
                  {s.name}{s.trust_level === 'test_confirmed' && <Check size={12} aria-hidden />}
                </span>
              ))}
            </div>
          )}
          {p.grade_source !== 'assessed' && p.survey_done && (
            <Link to="/candidate/assessment" className="btn-primary mt-5">Подтвердить грейд тестом</Link>
          )}
        </div>
        <div className="card">
          <h2 className="section-title">Что ещё сделать</h2>
          <ul className="mt-4 space-y-3 text-sm">
            {steps.map(s => (
              <li key={s.text} className="flex items-center gap-3">
                {s.done
                  ? <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ok text-white"><Check size={13} aria-hidden /></span>
                  : <Circle size={20} className="text-line-strong" aria-hidden />}
                {s.done || !s.to ? <span className={s.done ? 'text-ink-2' : 'text-ink'}>{s.text}</span>
                  : <Link to={s.to} className="text-accent hover:underline">{s.text}</Link>}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="card">
          <div className="flex items-baseline justify-between">
            <h2 className="section-title">Приглашения</h2>
            <Link to="/candidate/offers" className="text-sm text-accent hover:underline">Все</Link>
          </div>
          {pending.length === 0
            ? <p className="mt-4 text-sm text-ink-2">Новых приглашений нет. Работодатели пишут первыми: подтверждённый грейд и полный профиль поднимают вас в выдаче.</p>
            : <ul className="mt-3 divide-y divide-line">
                {pending.slice(0, 4).map(o => (
                  <li key={o.id} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                    <span><span className="font-medium text-ink">{o.company}</span> <span className="text-ink-2">{o.role}</span></span>
                    <span className="num text-sm text-ink">{rub(o.salary_from)} – {rub(o.salary_to)}</span>
                  </li>
                ))}
              </ul>}
        </div>
        <div className="card">
          <div className="flex items-baseline justify-between">
            <h2 className="section-title">Подтверждено ФСП</h2>
            <Link to="/candidate/results" className="text-sm text-accent hover:underline">Протоколы</Link>
          </div>
          {disciplines.length === 0
            ? <Empty title="Нет истории ФСП">Это не минус в выдаче. Если вы участвовали в соревнованиях, привяжите ФСП ID в профиле.</Empty>
            : <ul className="mt-4 space-y-4">
                {disciplines.map(d => (
                  <li key={d.discipline}>
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="text-ink">{d.label}</span>
                      <span className="flex items-center gap-2"><RankBadge rank={d.best_rank} />
                        <span className="num text-ink-2">{d.events_count} соревн.</span></span>
                    </div>
                    <div className="mt-2"><Meter value={Math.min(1, d.lcb / 0.6)} /></div>
                    <p className="mt-1 text-xs text-ink-3">Нижняя граница уровня {d.lcb.toFixed(2)}, уверенность {Math.round(d.confidence * 100)} %</p>
                  </li>
                ))}
              </ul>}
        </div>
      </section>
    </div>
  )
}
