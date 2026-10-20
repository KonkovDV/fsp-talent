import { useQuery } from '@tanstack/react-query'
import { myDisputes } from '../api/client'
import { date } from './ui'

/** The candidate's disputes with the methodist's answer and the deadline. Hidden while there are none. */
export default function MyDisputes() {
  const { data = [] } = useQuery({ queryKey: ['myDisputes'], queryFn: () => myDisputes().then(r => r.data) })
  if (data.length === 0) return null
  return (
    <section className="card" aria-labelledby="my-disputes">
      <h2 id="my-disputes" className="mb-2 text-sm font-semibold">Обращения</h2>
      <ul className="divide-y divide-border text-sm">
        {data.map(d => (
          <li key={d.id} className="space-y-1 py-2">
            <p className="flex flex-wrap justify-between gap-2">
              <span>Обращение от {date(d.created_at)}</span>
              <span className={d.status === 'open' ? 'text-ink-2' : 'font-medium text-ink'}>{d.status_label}</span>
            </p>
            {d.status === 'open' && <p className="text-xs text-ink-3">Ответ — не позднее {date(d.due_at)}</p>}
            {d.decision_note && <p className="text-ink-2">Ответ методиста: {d.decision_note}</p>}
            {d.status === 'voided' && (
              <p className="text-xs text-ink-3">Попытка не мешает пересдаче и не опускает грейд в подборке. Грейд по-прежнему ставит только тест.</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
