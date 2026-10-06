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
        lead="По нижней границе подтверждённого уровня: победы, призовые места и участие, их число и давность. Статус соревнования не учитывается, все соревнования весят одинаково. Здесь только те, кто сам открыл публичную страницу."
        actions={
          <select value={disc} onChange={e => setDisc(e.target.value)} className="select w-auto" aria-label="Дисциплина">
            <option value="">Все дисциплины</option>
            {Object.entries(DISC_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>} />
      {isLoading && <Skeleton className="h-96" />}
      {!isLoading && rows.length === 0 && <Empty title="В этой дисциплине пока никого">Участники попадают в рейтинг, когда включают публичную страницу.</Empty>}
      {rows.length >= 3 && (
        <ol className="mb-6 grid gap-4 sm:grid-cols-3" aria-label="Первые три места">
          {rows.slice(0, 3).map(r => (
            <li key={`top-${r.participant_id}-${r.discipline}`} className={r.rank === 1 ? 'hero-ink p-5' : 'card'}>
              <Link to={`/p/${r.participant_id}`} className="block">
                <span className={`font-display text-5xl font-bold leading-none num ${r.rank === 1 ? 'text-white' : 'text-accent'}`}>{r.rank}</span>
                <span className={`mt-4 block font-semibold ${r.rank === 1 ? 'text-white' : 'text-ink'}`}>{r.display_name}</span>
                <span className={`block text-sm ${r.rank === 1 ? 'on-hero-muted' : 'text-ink-2'}`}>{r.label ?? DISC_RU[r.discipline] ?? r.discipline}</span>
                <span className="mt-3 flex items-center gap-2">
                  <RankBadge rank={r.best_rank} />
                  <span className={`font-display text-sm font-bold num ${r.rank === 1 ? 'text-white' : 'text-ink'}`}>уровень {r.lcb.toFixed(2)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
      {rows.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="protocol">
            <thead><tr><th className="w-16 text-right">Место</th><th>Участник</th><th>Дисциплина</th><th>Разряд</th><th>Категория</th><th className="text-right">Уровень</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={`${r.participant_id}-${r.discipline}`}>
                  <td className="text-right"><span className={`place ${r.rank <= 3 ? 'text-accent' : 'text-ink-3'}`}>{r.rank}</span></td>
                  <td><Link to={`/p/${r.participant_id}`} className="font-medium text-ink hover:text-accent">{r.display_name}</Link>
                    <span className="block text-xs text-ink-3">{r.region}</span></td>
                  <td className="text-ink-2">{r.label ?? DISC_RU[r.discipline] ?? r.discipline}</td>
                  <td><RankBadge rank={r.best_rank} /></td>
                  <td className="text-ink-2">{r.primary_role ? `${ROLE_RU[r.primary_role] ?? r.primary_role}, ` : ''}{r.grade ?? ''}</td>
                  <td className="text-right">
                    <span className="inline-flex items-center gap-3">
                      <span className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-sunken sm:block" aria-hidden>
                        <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.round((r.lcb / (rows[0]?.lcb || 1)) * 100)}%` }} />
                      </span>
                      <span className="num font-semibold text-ink">{r.lcb.toFixed(2)}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PublicShell>
  )
}
