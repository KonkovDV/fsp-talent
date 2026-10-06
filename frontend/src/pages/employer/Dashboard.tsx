import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiError, getMyEmployerOffers, listNeeds, vacancyApplications } from '../../api/client'
import { PageHeader, plural } from '../../components/ui'

interface Need { id: string; title: string; version: number; shortlist_count: number }
interface OfferRow { status: string; candidate_viewed_at: string | null; contacts_revealed_at: string | null }

/** Employer home: three numbers that matter and the next step for each. */
export default function EmployerDashboard() {
  const offersQ = useQuery<OfferRow[]>({ queryKey: ['employerOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data) })
  const needsQ = useQuery<Need[]>({ queryKey: ['needs'], queryFn: () => listNeeds().then(r => r.data) })
  const appsQ = useQuery({ queryKey: ['applications'], queryFn: () => vacancyApplications().then(r => r.data) })
  const offers = offersQ.data ?? []
  const needs = needsQ.data ?? []
  const apps = appsQ.data ?? []
  const loadError = offersQ.error ?? needsQ.error ?? appsQ.error
  const accepted = offers.filter(o => o.status === 'accepted').length
  const pending = offers.filter(o => o.status === 'pending').length
  const funnel = [
    ['Отправлено', offers.length],
    ['Просмотрено', offers.filter(o => o.candidate_viewed_at).length],
    ['Принято', accepted],
    ['Контакты открыты', offers.filter(o => o.contacts_revealed_at).length],
  ] as const

  const tiles = [
    { n: needs.length, label: plural(needs.length, ['потребность', 'потребности', 'потребностей']), hint: 'Описание того, кого ищете, с подборкой и шорт-листом', to: '/employer/needs', cta: needs.length ? 'Открыть' : 'Создать первую' },
    { n: pending, label: `${plural(pending, ['приглашение ждёт', 'приглашения ждут', 'приглашений ждут'])} ответа`, hint: `Принято: ${accepted}. Контакты открываются после согласия`, to: '/employer/offers', cta: 'К приглашениям' },
    { n: apps.length, label: `${plural(apps.length, ['отклик', 'отклика', 'откликов'])} на вакансии`, hint: 'Кандидаты, которые откликнулись сами', to: '/employer/vacancies', cta: 'К вакансиям' },
  ]
  return (
    <div>
      <PageHeader title="Кабинет работодателя" lead="Начните с потребности: опишите роль и навыки — подборка с объяснением появится сразу."
        actions={<><Link to="/employer/search" className="btn-secondary">Свободный поиск</Link><Link to="/employer/needs" className="btn-primary">Новая потребность</Link></>} />
      {loadError && <p className="notice-error mb-4" role="alert">{apiError(loadError, 'Не удалось загрузить кабинет')}</p>}
      <section className="hero-ink mb-6 p-6 sm:p-8" aria-label="Воронка приглашений">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="font-display text-xl font-bold">Воронка приглашений</h2>
            <p className="mt-1 max-w-[52ch] text-sm on-hero-muted">
              {offers.length
                ? 'От отправки до открытых контактов. Контакты появляются только после согласия кандидата.'
                : 'Приглашений ещё нет. Опишите потребность — подборка с объяснением появится сразу, приглашать можно из неё.'}
            </p>
          </div>
          <Link to="/employer/needs" className="btn-on-hero">{needs.length ? 'К подборкам' : 'Описать потребность'}</Link>
        </div>
        <ol className="mt-8 grid grid-cols-2 gap-x-4 gap-y-6 sm:grid-cols-4">
          {funnel.map(([label, n], i) => {
            const top = funnel[0][1] || 1
            return (
              <li key={label}>
                <p className="font-display font-bold leading-none tracking-tight num [font-size:clamp(2.25rem,5vw,3.25rem)]">{n}</p>
                <p className="mt-2 text-sm on-hero-muted">{label}</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/20" aria-hidden>
                  <span className="block h-full rounded-full bg-white" style={{ width: `${offers.length ? Math.round((n / top) * 100) : 0}%`, opacity: 1 - i * 0.15 }} />
                </div>
              </li>
            )
          })}
        </ol>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        {tiles.map(t => (
          <Link key={t.label} to={t.to} className="card-hover flex flex-col">
            <span className="font-display text-4xl font-bold tabular-nums text-ink">{t.n}</span>
            <span className="mt-1 font-medium text-ink">{t.label}</span>
            <span className="mt-2 flex-1 text-sm text-ink-2">{t.hint}</span>
            <span className="mt-4 text-sm font-medium text-accent">{t.cta}</span>
          </Link>
        ))}
      </div>
      {needs.length > 0 && (
        <section className="mt-10">
          <h2 className="section-title">Потребности</h2>
          <ul className="mt-4 divide-y divide-line rounded-lg border border-line bg-panel">
            {needs.slice(0, 5).map(n => (
              <li key={n.id}><Link to="/employer/needs" className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-sunken/60">
                <span className="text-ink">{n.title}</span><span className="text-sm text-ink-3">версия {n.version}, в шорт-листе {n.shortlist_count}</span>
              </Link></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
