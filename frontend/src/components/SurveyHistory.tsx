import { useQuery } from '@tanstack/react-query'
import { surveyHistory } from '../api/client'
import { ROLE_RU, gradeRu } from '../labels'

type Row = { specialization: string; declared_grade: string; experience_years: number | null; created_at: string }

/** ТЗ 2.1: история опроса — каждое сохранение опроса, новые сверху. */
export default function SurveyHistory() {
  const q = useQuery({ queryKey: ['survey-history'], queryFn: () => surveyHistory().then(r => r.data as Row[]) })
  if (!q.data || q.data.length === 0) return null
  return (
    <section className="card space-y-3" aria-labelledby="survey-history-h" data-testid="survey-history">
      <h2 id="survey-history-h" className="section-title">История опроса</h2>
      <ul className="space-y-1 text-sm text-ink-2">
        {q.data.map(r => (
          <li key={r.created_at}>
            <span className="num">{new Date(r.created_at).toLocaleDateString('ru-RU')}</span>
            {' — '}{ROLE_RU[r.specialization] ?? r.specialization}, {gradeRu(r.declared_grade)}
            {r.experience_years != null && `, опыт ${r.experience_years} г.`}
          </li>
        ))}
      </ul>
    </section>
  )
}
