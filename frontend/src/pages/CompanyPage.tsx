import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getPublicCompany } from '../api/client'
import { ROLE_RU, gradeRu, industryRu } from '../labels'
import PublicShell from '../components/PublicShell'
import Responsiveness from '../components/Responsiveness'
import { Empty, Skeleton, rub } from '../components/ui'

interface VacancyRow {
  id: string; title: string; role: string | null; grade: string | null
  work_format: string; salary_from: number | null; salary_to: number | null
}

const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }

export default function CompanyPage() {
  const { id } = useParams<{ id: string }>()
  const query = useQuery({
    queryKey: ['company', id],
    queryFn: () => getPublicCompany(id!).then(r => r.data),
    enabled: !!id,
    retry: false,
  })
  if (query.isLoading) return <PublicShell><Skeleton className="h-64" /></PublicShell>
  if (query.isError || !query.data) {
    return <PublicShell><Empty title="Страница компании не опубликована" /></PublicShell>
  }
  const company = query.data
  return (
    <PublicShell>
      <article className="card space-y-4">
        <h1 className="font-display text-2xl font-bold text-ink">{company.name}</h1>
        <p className="text-sm text-ink-2">
          {[company.industry ? industryRu(company.industry) : null, company.trust_label].filter(Boolean).join(' · ')}
        </p>
        {company.rating && (
          <p className="text-sm text-ink-2">
            Балл компании {company.rating.score} из 10, {company.rating.label}. {company.rating.note}
          </p>
        )}
        <Responsiveness fact={company.reputation?.applications} className="text-sm text-ink-2" />
        {company.reputation?.acceptance?.shown && (
          <p className="text-sm text-ink-2" data-testid="acceptance">
            Приглашения компании принимают не реже {Math.round((company.reputation.acceptance.lower ?? 0) * 100)} % (по {company.reputation.acceptance.n} ответам)
          </p>
        )}
        {company.about && <p className="max-w-prose text-ink-2">{company.about}</p>}
        <p className="text-xs text-ink-3">
          {[company.website, company.inn_given ? 'ИНН указан' : 'ИНН не указан'].filter(Boolean).join(' · ')}
        </p>
        <h2 className="section-title">Открытые вакансии</h2>
        {(company.vacancies ?? []).length === 0
          ? <p className="text-sm text-ink-2">Открытых вакансий нет.</p>
          : (
            <ul className="space-y-2">
              {company.vacancies.map((row: VacancyRow) => (
                <li key={row.id} className="text-sm text-ink">
                  {row.title}
                  {row.role ? `, ${ROLE_RU[row.role] ?? row.role}` : ''}
                  {row.grade ? `, ${gradeRu(row.grade)}` : ''}
                  {row.work_format ? `, ${FORMAT[row.work_format] ?? row.work_format}` : ''}
                  {(row.salary_from != null || row.salary_to != null) && (
                    <span className="num"> · {rub(row.salary_from)} – {rub(row.salary_to)}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        <Link to="/login" className="btn-secondary btn-sm">Войти, чтобы откликнуться</Link>
      </article>
    </PublicShell>
  )
}
