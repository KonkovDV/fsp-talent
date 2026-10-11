import { Link } from 'react-router-dom'
import { ROLE_RU, gradeRu } from '../labels'

type Confirmation = { specialization: string; grade: string }

/** Extra categories confirmed by their own test. The survey category stays the primary one. */
export default function OtherCategories({ primary, confirmations }: { primary: string | null; confirmations: Confirmation[] }) {
  if (!primary) return null
  const extra = confirmations.filter(c => c.specialization !== primary)
  return (
    <section className="card" aria-labelledby="other-categories">
      <h2 id="other-categories" className="text-lg font-semibold">Дополнительные категории</h2>
      {extra.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-2">
          {extra.map(c => (
            <li key={c.specialization} className="chip">
              {ROLE_RU[c.specialization] ?? c.specialization} · {gradeRu(c.grade)} · подтверждено тестом
            </li>
          ))}
        </ul>
      ) : (
        <p className="field-hint mt-1">Пока только категория из опроса.</p>
      )}
      <p className="field-hint mt-2">
        Вторая специализация подтверждается отдельным тестом. Работодатель найдёт вас и по ней, категория из опроса не меняется.{' '}
        <Link to="/candidate/assessment" className="link">Пройти тест по другой специализации</Link>
      </p>
    </section>
  )
}
