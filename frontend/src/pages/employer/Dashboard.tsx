import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMyEmployerOffers, listNeeds, vacancyApplications } from '../../api/client'
import { PageHeader } from '../../components/ui'

interface Need { id: string; title: string; version: number; shortlist_count: number }

/** Employer home: three numbers that matter and the next step for each. */
export default function EmployerDashboard() {
  const { data: offers = [] } = useQuery({ queryKey: ['employerOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data) })
  const { data: needs = [] } = useQuery<Need[]>({ queryKey: ['needs'], queryFn: () => listNeeds().then(r => r.data) })
  const { data: apps = [] } = useQuery({ queryKey: ['applications'], queryFn: () => vacancyApplications().then(r => r.data) })
  const accepted = offers.filter((o: { status: string }) => o.status === 'accepted').length
  const pending = offers.filter((o: { status: string }) => o.status === 'pending').length

  const tiles = [
    { n: needs.length, label: 'потребностей', hint: 'Описание того, кого ищете, с подборкой и шорт-листом', to: '/employer/needs', cta: needs.length ? 'Открыть' : 'Создать первую' },
    { n: pending, label: 'приглашений ждут ответа', hint: `Принято: ${accepted}. Контакты открываются после согласия`, to: '/employer/offers', cta: 'К приглашениям' },
    { n: apps.length, label: 'откликов на вакансии', hint: 'Кандидаты, которые откликнулись сами', to: '/employer/vacancies', cta: 'К вакансиям' },
  ]
  return (
    <div>
      <PageHeader title="Кабинет работодателя" lead="Начните с потребности: опишите роль и навыки — подборка с объяснением появится сразу."
        actions={<><Link to="/employer/search" className="btn-secondary">Свободный поиск</Link><Link to="/employer/needs" className="btn-primary">Новая потребность</Link></>} />
      <div className="grid gap-4 md:grid-cols-3">
        {tiles.map(t => (
          <Link key={t.label} to={t.to} className="card-hover flex flex-col">
            <span className="font-display text-4xl font-semibold tabular-nums text-ink">{t.n}</span>
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
