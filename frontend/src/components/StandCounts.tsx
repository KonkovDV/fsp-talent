import { useQuery } from '@tanstack/react-query'
import { publicStats, type StandStats } from '../api/client'

const ITEMS: [keyof StandStats, string][] = [
  ['candidates', 'кандидатов на стенде'],
  ['with_fsp', 'с результатами ФСП'],
  ['families', 'семейств заданий'],
  ['companies', 'компаний'],
]

/** Four live totals from /public/stats. Nothing is shown while loading or on error: no made-up numbers. */
export default function StandCounts() {
  const { data } = useQuery({
    queryKey: ['public-stats'], retry: false, staleTime: 60_000,
    queryFn: () => publicStats().then(r => r.data),
  })
  if (!data) return null
  return (
    <dl data-testid="stand-counts" className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
      {ITEMS.map(([key, label]) => (
        <div key={key} className="flex flex-col-reverse">
          <dt className="text-xs text-white/85">{label}</dt>
          <dd className="font-display text-3xl font-bold">{data[key].toLocaleString('ru-RU')}</dd>
        </div>
      ))}
    </dl>
  )
}
