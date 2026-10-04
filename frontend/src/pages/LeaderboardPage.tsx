import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLeaderboard } from '../api/client'
import { Link } from 'react-router-dom'
import { Trophy } from 'lucide-react'

const DISC: Record<string, string> = {
  '': 'Все дисциплины', algorithmic: 'Алгоритмика', product: 'Продукт',
  security: 'Безопасность', bas: 'БАС', robotics: 'Робототехника',
}
const GRADE_CLASS: Record<string, string> = { lead: 'badge-lead', senior: 'badge-senior', middle: 'badge-middle', junior: 'badge-junior' }

export default function LeaderboardPage() {
  const [disc, setDisc] = useState('')
  const { data: rows = [] } = useQuery({
    queryKey: ['leaderboard', disc],
    queryFn: () => getLeaderboard(disc || undefined).then(r => r.data)
  })
  return (
    <div className="min-h-screen bg-fsp-light-bg">
      <header className="bg-fsp-dark text-white py-4">
        <div className="max-w-5xl mx-auto px-6 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-fsp-violet">FSP Talent</Link>
          <Link to="/login" className="text-sm text-gray-400 hover:text-white">Войти</Link>
        </div>
      </header>
      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="flex items-center gap-4 mb-6">
          <Trophy className="text-amber-500" size={28} />
          <h1 className="text-3xl font-bold">Лидерборд</h1>
          <select value={disc} onChange={e => setDisc(e.target.value)}
            className="ml-auto border border-gray-200 rounded-xl px-3 py-2 text-sm">
            {Object.entries(DISC).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
        <div className="space-y-3">
          {rows.map((r: any) => (
            <Link to={`/p/${r.participant_id}`} key={r.participant_id}
              className="card-hover flex items-center gap-4">
              <span className={`text-lg font-bold w-8 ${
                r.rank === 1 ? 'text-amber-500' : r.rank === 2 ? 'text-gray-400' : r.rank === 3 ? 'text-amber-700' : 'text-gray-400'
              }`}>#{r.rank}</span>
              <div className="flex-1">
                <p className="font-semibold">{r.display_name}</p>
                <p className="text-sm text-text-muted">{r.region} · {r.label ?? r.discipline}</p>
              </div>
              {r.best_rank && <span className="badge bg-amber-50 text-amber-800">{r.best_rank}</span>}
              {r.grade && <span className={GRADE_CLASS[r.grade] ?? 'badge'}>{r.grade}</span>}
              <span className="text-lg font-bold text-fsp-violet font-mono">{r.lcb.toFixed(2)}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
