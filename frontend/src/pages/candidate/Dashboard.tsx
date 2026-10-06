import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Check, Circle } from 'lucide-react'
import { getMyOffers, getMyProfile } from '../../api/client'
import SurveyCard from '../../components/SurveyCard'
import { Empty, Meter, PageHeader, RankBadge, SOURCE_LABEL, Skeleton, rub } from '../../components/ui'
import { ROLE_RU } from '../../labels'

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
        <div className="hero-ink p-6 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm on-hero-muted">Ваша категория в выдаче</p>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${p.grade_source === 'assessed' ? 'bg-white text-[#2A1DD6]' : 'border border-white/50 text-white'}`}>
              {p.grade_source === 'assessed' ? 'грейд подтверждён тестом' : `грейд: ${SOURCE_LABEL[p.grade_source] ?? 'не указан'}`}
            </span>
          </div>
          <p className="mt-6 font-display text-xl font-bold sm:text-2xl">{ROLE_RU[p.primary_role] ?? p.primary_role ?? 'Специализация не выбрана'}</p>
          <p className="font-display font-bold leading-none tracking-[-0.04em] [font-size:clamp(3.25rem,8vw,5.5rem)]">{p.grade ?? '—'}</p>
          {(p.skills ?? []).length > 0 && (
            <ul className="mt-6 flex flex-wrap gap-1.5" aria-label="Навыки">
              {(p.skills ?? []).slice(0, 12).map((sk: { name: string; trust_level: string }) => (
                <li key={sk.name} className={`chip-on-hero ${sk.trust_level === 'test_confirmed' ? '!bg-white !text-[#2A1DD6]' : ''}`}
                  title={sk.trust_level === 'test_confirmed' ? 'Подтверждён тестом' : sk.trust_level === 'resume_confirmed' ? 'Цитата из резюме' : 'Заявлен'}>
                  {sk.name}{sk.trust_level === 'test_confirmed' && <Check size={12} aria-hidden />}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-7 flex flex-wrap items-center gap-3">
            {p.survey_done && (
              <Link to="/candidate/assessment" className="btn-on-hero">
                {p.grade_source === 'assessed' ? 'Подтвердить грейд выше' : 'Подтвердить грейд тестом'}
              </Link>
            )}
            <p className="max-w-[40ch] text-sm on-hero-muted">
              {p.grade_source === 'assessed'
                ? 'Работодатель видит отметку «подтверждён тестом» и ставит вас выше заявленных грейдов.'
                : 'Подтверждённый тестом грейд стоит в выдаче выше заявленного. 8–20 заданий, до 3 минут на каждое.'}
            </p>
          </div>
        </div>
        <div className="card">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="section-title">Готовность профиля</h2>
            <span className="font-display text-sm font-bold text-ink num">{steps.filter(st => st.done).length} из {steps.length}</span>
          </div>
          <div className="mt-3 grid grid-cols-5 gap-1" aria-hidden>
            {steps.map(st => <span key={st.text} className={`h-1.5 rounded-full ${st.done ? 'bg-accent' : 'bg-sunken'}`} />)}
          </div>
          <ul className="mt-5 space-y-3 text-sm">
            {steps.map(st => (
              <li key={st.text} className="flex items-center gap-3">
                {st.done
                  ? <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ok text-white"><Check size={13} aria-hidden /></span>
                  : <Circle size={20} className="shrink-0 text-line-strong" aria-hidden />}
                {st.done || !st.to ? <span className={st.done ? 'text-ink-2' : 'text-ink'}>{st.text}</span>
                  : <Link to={st.to} className="font-medium text-accent hover:underline">{st.text}</Link>}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="card">
          <div className="flex items-baseline justify-between">
            <h2 className="section-title">Приглашения{pending.length > 0 && <span className="ml-2 rounded-full bg-invite px-2 py-0.5 align-middle font-sans text-xs text-invite-ink num">{pending.length}</span>}</h2>
            <Link to="/candidate/offers" className="text-sm text-accent hover:underline">Все</Link>
          </div>
          {pending.length === 0
            ? <p className="mt-4 text-sm text-ink-2">Новых приглашений нет. Работодатели пишут первыми: подтверждённый грейд и полный профиль поднимают вас в выдаче.</p>
            : <ul className="mt-3 divide-y divide-line">
                {pending.slice(0, 4).map(o => (
                  <li key={o.id}>
                    <Link to="/candidate/offers" className="-mx-2 flex items-center gap-3 rounded-md px-2 py-3 hover:bg-sunken">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-accent-soft font-display text-base font-bold text-accent" aria-hidden>
                        {o.company.slice(0, 1)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-ink">{o.role}</span>
                        <span className="block truncate text-sm text-ink-2">{o.company}</span>
                      </span>
                      <span className="text-right font-display text-sm font-bold text-ink num">{rub(o.salary_from)}<span className="block text-xs font-normal text-ink-3">до {rub(o.salary_to)}</span></span>
                    </Link>
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
                    <div className="mt-2"><Meter value={Math.min(1, d.lcb / 0.6)} ariaLabel={`Уровень по результатам ФСП, ${d.label}`} /></div>
                    <p className="mt-1 text-xs text-ink-3">Нижняя граница уровня {d.lcb.toFixed(2)}, уверенность {Math.round(d.confidence * 100)} %</p>
                  </li>
                ))}
              </ul>}
        </div>
      </section>
    </div>
  )
}
