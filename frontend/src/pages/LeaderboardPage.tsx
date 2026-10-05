import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getLeaderboard } from '../api/client'
import { DISC_RU, ROLE_RU } from '../labels'
import PublicShell from '../components/PublicShell'
import { Empty, PageHeader, RankBadge, Skeleton } from '../components/ui'

interface Row { participant_id: string; rank: number; display_name: string; region: string | null; label?: string; discipline: string
  best_rank: string | null; grade: string | null; primary_role?: string | null; lcb: number }

/** Public rating: only adults who gave a separate consent to publish their data (152-FZ art. 10.1). */
export default function LeaderboardPage() {
  const [disc, setDisc] = useState('')
  const { data: rows = [], isLoading } = useQuery<Row[]>({ queryKey: ['leaderboard', disc], queryFn: () => getLeaderboard(disc || undefined).then(r => r.data) })
  return (
    <PublicShell>
      <PageHeader title="Рейтинг участников ФСП"
        lead="По нижней границе подтверждённого уровня: место в протоколе, размер поля, разряд и давность. Здесь только те, кто сам открыл публичную страницу."
        actions={
          <select value={disc} onChange={e => setDisc(e.target.value)} className="select w-auto" aria-label="Дисциплина">
            <option value="">Все дисциплины</option>
            {Object.entries(DISC_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>} />
      {isLoading && <Skeleton className="h-96" />}
      {!isLoading && rows.length === 0 && <Empty title="В этой дисциплине пока никого">Участники попадают в рейтинг, когда включают публичную страницу.</Empty>}
      {rows.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="protocol">
            <thead><tr><th className="w-16 text-right">Место</th><th>Участник</th><th>Дисциплина</th><th>Разряд</th><th>Категория</th><th className="text-right">Уровень</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={`${r.participant_id}-${r.discipline}`}>
                  <td className="text-right"><span className={`place ${r.rank <= 3 ? 'text-medal' : 'text-ink-3'}`}>{r.rank}</span></td>
                  <td><Link to={`/p/${r.participant_id}`} className="font-medium text-ink hover:text-accent">{r.display_name}</Link>
                    <span className="block text-xs text-ink-3">{r.region}</span></td>
                  <td className="text-ink-2">{r.label ?? DISC_RU[r.discipline] ?? r.discipline}</td>
                  <td><RankBadge rank={r.best_rank} /></td>
                  <td className="text-ink-2">{r.primary_role ? `${ROLE_RU[r.primary_role] ?? r.primary_role}, ` : ''}{r.grade ?? ''}</td>
                  <td className="num text-right font-semibold text-ink">{r.lcb.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PublicShell>
  )
}
