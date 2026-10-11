import { useEffect, useState } from 'react'
import { publicStats, type StandStats } from '../api/client'

const ITEMS: [keyof StandStats, string][] = [
  ['candidates', 'кандидатов на стенде'],
  ['with_fsp', 'с результатами ФСП'],
  ['families', 'семейств заданий'],
  ['companies', 'компаний'],
]

/**
 * Four live totals from /public/stats. The landing page sits outside QueryShell (React Query loads
 * with the next route), so this uses a plain effect. Nothing is shown while loading or on error.
 */
export default function StandCounts() {
  const [data, setData] = useState<StandStats | null>(null)
  useEffect(() => {
    let alive = true
    publicStats().then(r => { if (alive) setData(r.data) }).catch(() => {})
    return () => { alive = false }
  }, [])
  if (!data) return null
  return (
    <dl data-testid="stand-counts" className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
      {ITEMS.map(([key, label]) => (
        <div key={key} className="flex min-w-0 flex-col-reverse justify-end">
          <dt className="text-xs text-white/85">{label}</dt>
          <dd className="font-display text-3xl font-bold">{Number(data[key]).toLocaleString('ru-RU')}</dd>
        </div>
      ))}
    </dl>
  )
}
