import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CalendarClock, Check, Circle, ClipboardList } from 'lucide-react'
import { apiError, getMyGrowth, getMyOffers, getMyProfile, getMySalaryMarket, myCareer, tasksForMe, weeklyTask } from '../../api/client'
import { TaskResult } from './Tasks'
import SurveyCard from '../../components/SurveyCard'
import GuardianCard from '../../components/GuardianCard'
import DemoResetCard from '../../components/DemoResetCard'
import { Empty, Meter, PageHeader, RankBadge, SOURCE_LABEL, Skeleton, plural, rub } from '../../components/ui'
import { netLine } from '../../money'
import { ROLE_RU, gradeRu } from '../../labels'

interface Disc { discipline: string; label: string; score?: number; lcb: number; confidence: number; best_rank: string | null; rank_assigned_at?: string | null; rank_order_ref?: string | null; events_count: number }
interface Offer { id: string; company: string; role: string; salary_from: number; salary_to: number; status: string }
interface Weekly { vacancy_id: string; title: string; company: string | null; topic_label: string | null; done: boolean; is_correct: boolean | null; week_from: string }
interface MarketCell { p25: number; median: number; p75: number; n: number }
interface SalaryMarket { role: string | null; grade: string | null; cell: MarketCell | null; band: string | null }
interface Growth { role: string | null; grade: string | null; next_grade: string | null; people: number | null
  gaps: { skill: string; people: number }[]
  need_reach?: { skill: string; needs: number }[]
  next_market: MarketCell | null }

const BAND_TEXT: Record<string, string> = {
  below_p25: 'Ваше ожидание ниже нижней четверти.',
  below_median: 'Ваше ожидание ниже середины шкалы.',
  through_p75: 'Ваше ожидание не выше верхней четверти.',
  above_p75: 'Ваше ожидание выше верхней четверти.',
}

/** Candidate home: the category employers see, what is missing for it, and fresh invitations. */
export default function CandidateDashboard() {
  const profile = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const offersQ = useQuery<Offer[]>({ queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data) })
  const { data: weekly } = useQuery<Weekly | null>({ queryKey: ['weeklyTask'], queryFn: () => weeklyTask().then(r => r.data) })
  const career = useQuery({ queryKey: ['myCareer'], queryFn: () => myCareer().then(r => r.data) })
  const { data: tasks = [], isError: tasksError, error: tasksLoadError } = useQuery({ queryKey: ['tasksForMe'], queryFn: () => tasksForMe().then(r => r.data) })
  const market = useQuery<SalaryMarket>({ queryKey: ['salaryMarket'], queryFn: () => getMySalaryMarket().then(r => r.data) })
  const growth = useQuery<Growth>({ queryKey: ['growth'], queryFn: () => getMyGrowth().then(r => r.data) })
  const p = profile.data
  const offers = offersQ.data ?? []

  if (profile.isLoading) return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-48" /><Skeleton className="h-64" /></div>
  if (profile.isError || !p) return <p className="notice-error" role="alert">{apiError(profile.error, 'Не удалось открыть кабинет')}</p>

  const pending = offers.filter(o => o.status === 'pending')
  const completeness = p.completeness as {
    percent: number; done: number; total: number
    items: { code: string; label: string; done: boolean; href: string | null }[]
  } | undefined
  const steps = completeness?.items ?? []
  const disciplines: Disc[] = p.discipline_scores ?? []

  return (
    <div className="space-y-6">
      <PageHeader title={p.display_name ? `Здравствуйте, ${p.display_name.split(' ')[0]}` : 'Кабинет'}
        lead="Так вас видит работодатель в поиске: без имени и контактов, по категории и подтверждениям." />

      {p.is_minor && !p.minor_consent_given && (
        <GuardianCard sentTo={p.guardian_email ?? null} demoLink={p.guardian_demo_link ?? null} />
      )}
      {p.search_blocker === 'birth_date_missing' && (
        <p className="notice-info" role="status" data-testid="birth-date-missing">
          Работодатели пока не видят вас в поиске: укажите дату рождения в <Link to="/candidate/profile" className="underline">профиле</Link>. Отметка «18 лет» возраст не подтверждает.
        </p>
      )}
      {p.demo_reset_available && <DemoResetCard />}
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
          <p className="font-display font-bold leading-none tracking-[-0.04em] [font-size:clamp(3.25rem,8vw,5.5rem)]">{p.grade ? gradeRu(p.grade) : '—'}</p>
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
            <span className="font-display text-sm font-bold text-ink num" data-testid="profile-completeness">
              {completeness ? `${completeness.percent} %, ${completeness.done} из ${completeness.total}` : '—'}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-8 gap-1" aria-hidden>
            {steps.map(st => <span key={st.code} className={`h-1.5 rounded-full ${st.done ? 'bg-accent' : 'bg-sunken'}`} />)}
          </div>
          <ul className="mt-5 space-y-3 text-sm">
            {steps.map(st => (
              <li key={st.code} className="flex items-center gap-3">
                {st.done
                  ? <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ok text-white"><Check size={13} aria-hidden /></span>
                  : <Circle size={20} className="shrink-0 text-line-strong" aria-hidden />}
                {st.done || !st.href ? <span className={st.done ? 'text-ink-2' : 'text-ink'}>{st.label}</span>
                  : <Link to={st.href} className="font-medium text-accent hover:underline">{st.label}</Link>}
              </li>
            ))}
          </ul>
          {(career.data?.gained ?? 0) > 0 && (
            <p className="mt-4 text-sm text-ink-2">Если подтвердить «{career.data?.skill}» тестом, закроется ещё {career.data?.gained} открытых вакансий. Грейд от этого сам не вырастет.</p>
          )}
          <p className="mt-4 text-xs text-ink-3">
            {p.has_fsp ? 'ФСП ID привязан.' : 'ФСП ID не привязан: на заполненность это не влияет.'}
            {' '}{p.birth_date ? '' : 'Чтобы работодатели вас видели, привяжите ФСП ID или укажите дату рождения. '}
            {p.certificate_grade ? ` Сертификат называет грейд «${gradeRu(p.certificate_grade)}». В поиск и в подтверждённый грейд он не входит.` : ''}
            {' '}{p.discoverable ? 'Карточка видна работодателям.' : 'Карточка скрыта из поиска.'}
          </p>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]" aria-label="Приглашения и результаты ФСП">
        <div className="card relative overflow-hidden">
          {pending.length > 0 && <span className="absolute inset-y-0 left-0 w-[3px] bg-invite" aria-hidden />}
          <div className="card-head">
            <h2 className="section-title flex items-center gap-2">Приглашения{pending.length > 0 && <span className="count-invite">{pending.length}</span>}</h2>
            <Link to="/candidate/offers" className="link text-sm">Все приглашения</Link>
          </div>
          {offersQ.isError
            ? <p className="notice-error mt-4" role="alert">{apiError(offersQ.error, 'Не удалось загрузить приглашения')}</p>
            : pending.length === 0
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
                      <span className="text-right font-display text-sm font-bold text-ink num">{rub(o.salary_from)}<span className="block text-xs font-normal text-ink-3">до {rub(o.salary_to)}, до НДФЛ</span><span className="block text-xs font-normal text-ink-3">{netLine(o.salary_from, o.salary_to)}</span></span>
                    </Link>
                  </li>
                ))}
              </ul>}
        </div>
        <div className="card">
          <div className="card-head">
            <h2 className="section-title">Подтверждено ФСП</h2>
            <Link to="/candidate/results" className="link text-sm">Протоколы</Link>
          </div>
          {disciplines.length === 0
            ? <Empty title="Нет истории ФСП">Это не минус в выдаче. Если вы участвовали в соревнованиях, привяжите ФСП ID в профиле.</Empty>
            : <ul className="mt-4 space-y-4">
                {disciplines.map(d => (
                  <li key={d.discipline}>
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="text-ink">{d.label}</span>
                      <span className="flex items-center gap-2">
                        <RankBadge rank={d.best_rank} assignedAt={d.rank_assigned_at} orderRef={d.rank_order_ref} />
                        {d.best_rank && <span className="text-ink-3">Присвоенный разряд</span>}
                        <span className="num text-ink-2">{d.events_count} соревн.</span></span>
                    </div>
                    <div className="mt-2"><Meter value={Math.min(1, d.lcb / 0.6)} ariaLabel={`Уровень по результатам ФСП, ${d.label}`} /></div>
                    <p className="mt-1 text-xs text-ink-3">Нижняя граница уровня {d.lcb.toFixed(2)}, уверенность {Math.round(d.confidence * 100)} %</p>
                  </li>
                ))}
              </ul>}
        </div>
      </section>

      <section className={`grid items-start gap-6 ${weekly ? 'lg:grid-cols-[1.4fr_1fr]' : ''}`} aria-label="Задания">
        <section className="card" aria-labelledby="tasks-title">
        <div className="card-head">
          <h2 id="tasks-title" className="section-title flex items-center gap-2">
            <ClipboardList size={18} className="text-accent" aria-hidden />Задания от работодателей
            {tasks.filter(t => t.accepts_answers).length > 0 && <span className="count">{tasks.filter(t => t.accepts_answers).length}</span>}
          </h2>
          <Link to="/candidate/tasks" className="link text-sm">Все задания</Link>
        </div>
        {tasksError
          ? <p className="notice-error mt-3" role="alert">{apiError(tasksLoadError, 'Не удалось загрузить задания')}</p>
          : tasks.length === 0
          ? <p className="mt-3 text-sm text-ink-2">Компании пишут задания сами: для всех кандидатов специализации или лично вам. Новых заданий пока нет.</p>
          : <ul className="mt-3 divide-y divide-line">
              {tasks.slice(0, 3).map(t => (
                <li key={t.id}>
                  <Link to={`/candidate/tasks?task=${t.id}`} className="-mx-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md px-2 py-3 hover:bg-sunken">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-ink">{t.title}</span>
                      <span className="block truncate text-sm text-ink-2">{t.company ? `«${t.company}»` : 'Работодатель'}{t.addressed ? ', лично вам' : ''}</span>
                    </span>
                    {t.submission ? <TaskResult task={t} /> : <span className="badge-brand">ждёт ответа</span>}
                  </Link>
                </li>
              ))}
            </ul>}
        </section>

      {weekly && (
        <section className="card flex flex-col items-start gap-4" aria-labelledby="weekly-title">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-xs text-ink-3"><CalendarClock size={14} aria-hidden />Сгенерировано платформой</p>
            <h2 id="weekly-title" className="section-title mt-1">Задача недели по вакансии{weekly.company ? ` компании «${weekly.company}»` : ''}</h2>
            <p className="mt-1 text-sm text-ink-2">
              Платформа собрала одно задание{weekly.topic_label ? ` по теме «${weekly.topic_label}»` : ''} по тексту вакансии «{weekly.title}»;
              сама компания его не писала. Грейд оно не меняет, а работодатели увидят в карточке свежий результат и его дату.
            </p>
          </div>
          {weekly.done
            ? <span className={`badge shrink-0 ${weekly.is_correct ? 'badge-ok' : 'badge-warn'}`}>Решена{weekly.is_correct ? ' верно' : ', есть ошибка'}</span>
            : <Link to={`/candidate/vacancies?vacancy=${weekly.vacancy_id}`} className="btn-secondary shrink-0">Решить задачу</Link>}
        </section>
      )}

      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1.4fr_1fr]">
      {market.data?.role && market.data.grade && (
        <section className="card" aria-labelledby="market-title">
          <h2 id="market-title" className="section-title">Ожидания в вашей категории</h2>
          <p className="mt-1 text-sm text-ink-2">{ROLE_RU[market.data.role] ?? market.data.role}, {gradeRu(market.data.grade)}. Чужие суммы по отдельности не показываются.</p>
          {market.data.cell ? (
            <>
              <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                <div><dt className="text-xs text-ink-3">Нижняя четверть</dt><dd className="num font-display text-lg font-bold text-ink">{rub(market.data.cell.p25)}</dd></div>
                <div><dt className="text-xs text-ink-3">Середина</dt><dd className="num font-display text-lg font-bold text-ink">{rub(market.data.cell.median)}</dd></div>
                <div><dt className="text-xs text-ink-3">Верхняя четверть</dt><dd className="num font-display text-lg font-bold text-ink">{rub(market.data.cell.p75)}</dd></div>
              </dl>
              <p className="mt-3 text-sm text-ink-2">
                По {market.data.cell.n} названным ожиданиям.{' '}
                {market.data.band
                  ? BAND_TEXT[market.data.band]
                  : <><Link to="/candidate/profile" className="font-medium text-accent underline">Укажите нижнюю границу в опросе</Link>, чтобы увидеть своё место на шкале.</>}
              </p>
            </>
          ) : (
            <p className="mt-3 text-sm text-ink-2">В этой категории меньше пяти названных ожиданий, поэтому шкала скрыта.</p>
          )}
        </section>
      )}

      {growth.data?.next_grade && (
        <section className="card" aria-labelledby="growth-title">
          <h2 id="growth-title" className="section-title">Путь к следующему грейду</h2>
          <p className="mt-1 text-sm text-ink-2">
            {gradeRu(growth.data.next_grade)}, {ROLE_RU[growth.data.role ?? ''] ?? growth.data.role}. Этот список грейд не меняет: грейд даёт только тест.
          </p>
          {growth.data.people == null ? (
            <p className="mt-3 text-sm text-ink-2">На следующей ступени меньше пяти видимых профилей, поэтому список скрыт.</p>
          ) : growth.data.gaps.length === 0 ? (
            <p className="mt-3 text-sm text-ink-2">По навыкам этой специализации вы уже закрываете то, что на следующей ступени называют не меньше пяти человек.</p>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {growth.data.gaps.map(gap => (
                <li key={gap.skill} className="flex items-baseline justify-between gap-3 py-2 text-sm">
                  <span className="font-medium text-ink">{gap.skill}</span>
                  <span className="num shrink-0 text-ink-3">{gap.people} {plural(gap.people, ['человек', 'человека', 'человек'])}</span>
                </li>
              ))}
            </ul>
          )}
          {growth.data.next_market && (
            <p className="mt-3 text-sm text-ink-2">Середина названных ожиданий на следующей ступени — {rub(growth.data.next_market.median)}. По {growth.data.next_market.n} {plural(growth.data.next_market.n, ['ожиданию', 'ожиданиям', 'ожиданиям'])}.</p>
          )}
          <p className="mt-3 text-sm"><Link to="/candidate/profile" className="link">Добавить навык в профиле</Link></p>
        </section>
      )}

      {(growth.data?.need_reach ?? []).length > 0 && (
        <section className="card" aria-labelledby="reach-title">
          <h2 id="reach-title" className="section-title">Одна технология до открытой потребности</h2>
          <p className="mt-1 text-sm text-ink-2">Обязательные навыки той же специализации. Если не хватает ровно одного, потребность считается. Грейд и место в подборке это не меняет.</p>
          <ul className="mt-4 divide-y divide-line">
            {(growth.data?.need_reach ?? []).map(row => (
              <li key={row.skill} className="flex items-baseline justify-between gap-3 py-2 text-sm">
                <span className="font-medium text-ink">{row.skill}</span>
                <span className="num shrink-0 text-ink-3">{row.needs} {plural(row.needs, ['потребность', 'потребности', 'потребностей'])}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      </div>
    </div>
  )
}
