import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { apiError, getMyResults, presentResult } from '../../api/client'
import { Empty, PageHeader, RankBadge, Skeleton, date } from '../../components/ui'

interface Row {
  id: string; event_name: string; discipline_label: string; status_label: string; place: number
  total_participants: number; rank_equivalent: string | null; is_team: boolean; team_size: number
  event_date: string; protocol_url: string | null; ekp_number?: string | null
}

/** Competition protocols as a protocol: place first, field size next to it. */
export default function CandidateResults() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState<string | null>(null)
  const [cardError, setCardError] = useState('')
  const { data: rows = [], isLoading, isError, error } = useQuery<Row[]>({ queryKey: ['myResults'], queryFn: () => getMyResults().then(r => r.data) })
  const openCard = async (id: string) => {
    setBusy(id)
    setCardError('')
    try {
      const { data } = await presentResult(id)
      sessionStorage.setItem('fsp-badge', JSON.stringify(data.credential))
      navigate('/badge')
    } catch (err) {
      setCardError(apiError(err, 'Не удалось собрать карточку'))
    } finally {
      setBusy(null)
    }
  }
  return (
    <div>
      <PageHeader title="Результаты ФСП"
        lead="Места из официальных протоколов. Каждый результат подписан удостоверением, работодатель видит год, уровень соревнования и процентиль без названия события." />
      {isLoading && <Skeleton className="h-64" />}
      {isError && <p className="notice-error mb-4" role="alert">{apiError(error, 'Не удалось загрузить протоколы')}</p>}
      {cardError && <p className="notice-error mb-4" role="alert">{cardError}</p>}
      {!isLoading && !isError && rows.length === 0 && (
        <Empty title="Протоколов пока нет">Привяжите ФСП ID в профиле — результаты подтянутся автоматически. Без них категория строится по опросу и тесту.</Empty>
      )}
      {rows.length > 0 && (
        <div className="card overflow-x-auto p-0" tabIndex={0} role="region" aria-label="Таблица результатов">
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
                    <button type="button" className="mt-0.5 inline-flex min-h-6 items-center text-xs font-medium text-accent underline" disabled={busy === r.id} onClick={() => openCard(r.id)}>Краткое удостоверение</button>
                    <p className="text-xs text-ink-3">{r.status_label}{r.is_team ? `, команда из ${r.team_size}` : ''}{r.ekp_number ? `. ${r.ekp_number.startsWith('ЕКП-демо') ? 'Демо-номер календаря' : 'Номер в календаре ЕКП'}: ${r.ekp_number}` : ''}</p>
                  </td>
                  <td className="text-ink-2">{r.discipline_label}</td>
                  <td><RankBadge rank={r.rank_equivalent} /></td>
                  <td className="num whitespace-nowrap text-right text-ink-2">
                    {date(r.event_date)}
                    {r.protocol_url && <a href={r.protocol_url} target="_blank" rel="noreferrer" className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded text-accent hover:bg-accent-soft" aria-label="Протокол"><ExternalLink size={14} aria-hidden /></a>}
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
