import { useQuery } from '@tanstack/react-query'
import { getMyResults } from '../../api/client'
import { Medal } from 'lucide-react'

const STATUS_COLOR: Record<string, string> = {
  world: 'bg-purple-100 text-purple-800',
  russia_championship: 'bg-yellow-100 text-yellow-800',
  russia_cup: 'bg-amber-100 text-amber-800',
  russia_youth: 'bg-blue-100 text-blue-800',
  all_russian: 'bg-sky-100 text-sky-800',
  federal_district: 'bg-indigo-100 text-indigo-800',
  regional: 'bg-green-100 text-green-800',
  other: 'bg-gray-100 text-gray-700',
}

export default function CandidateResults() {
  const { data: results = [], isLoading } = useQuery({
    queryKey: ['myResults'], queryFn: () => getMyResults().then(r => r.data)
  })
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Результаты ФСП</h1>
      {isLoading && <div className="animate-pulse h-40 bg-gray-100 rounded-2xl" />}
      {results.map((r: any) => (
        <div key={r.id} className="card flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
            <Medal size={20} className="text-amber-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-text-primary truncate">{r.event_name}</p>
            <div className="flex flex-wrap gap-2 mt-1">
              <span className={`badge ${STATUS_COLOR[r.competition_status] ?? 'bg-gray-100 text-gray-700'}`}>{r.status_label}</span>
              <span className="badge bg-fsp-violet/10 text-fsp-violet">{r.discipline_label}</span>
              {r.rank_equivalent && <span className="badge bg-amber-50 text-amber-800">{r.rank_equivalent}</span>}
              {r.is_team && <span className="badge bg-gray-100 text-gray-600">команда {r.team_size}</span>}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-fsp-violet">{r.place}</p>
            <p className="text-xs text-gray-400">of {r.total_participants}</p>
            <p className="text-xs text-gray-400 mt-1">{r.event_date}</p>
          </div>
        </div>
      ))}
      {!isLoading && results.length === 0 && (
        <div className="card text-center text-gray-400 py-12">Результатов пока нет</div>
      )}
    </div>
  )
}
