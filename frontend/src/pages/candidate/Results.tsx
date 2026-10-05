import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { getMyResults } from '../../api/client'
import { Empty, PageHeader, RankBadge, Skeleton, date } from '../../components/ui'

interface Row {
  id: string; event_name: string; discipline_label: string; status_label: string; place: number
  total_participants: number; rank_equivalent: string | null; is_team: boolean; team_size: number
  event_date: string; protocol_url: string | null
}

/** Competition protocols as a protocol: place first, field size next to it. */
export default function CandidateResults() {
  const { data: rows = [], isLoading } = useQuery<Row[]>({ queryKey: ['myResults'], queryFn: () => getMyResults().then(r => r.data) })
  return (
    <div>
      <PageHeader title="Результаты ФСП"
        lead="Места из официальных протоколов. Каждый результат подписан удостоверением, работодатель видит год, уровень соревнования и процентиль без названия события." />
      {isLoading && <Skeleton className="h-64" />}
      {!isLoading && rows.length === 0 && (
        <Empty title="Протоколов пока нет">Привяжите ФСП ID в профиле — результаты подтянутся автоматически. Без них категория строится по опросу и тесту.</Empty>
      )}
      {rows.length > 0 && (
        <div className="card overflow-x-auto p-0">
          <table className="protocol">
            <thead><tr>
              <th className="w-20 text-right">Место</th><th>Соревнование</th><th>Дисциплина</th><th>Разряд</th><th className="text-right">Дата</th>
            </tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td className="text-right"><span className="place">{r.place}</span><span className="num block text-xs text-ink-3">из {r.total_participants}</span></td>
                  <td>
                    <p className="font-medium text-ink">{r.event_name}</p>
                    <p className="text-xs text-ink-3">{r.status_label}{r.is_team ? `, команда из ${r.team_size}` : ''}</p>
                  </td>
                  <td className="text-ink-2">{r.discipline_label}</td>
                  <td><RankBadge rank={r.rank_equivalent} /></td>
                  <td className="num whitespace-nowrap text-right text-ink-2">
                    {date(r.event_date)}
                    {r.protocol_url && <a href={r.protocol_url} target="_blank" rel="noreferrer" className="ml-2 inline-flex text-accent" aria-label="Протокол"><ExternalLink size={14} /></a>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
