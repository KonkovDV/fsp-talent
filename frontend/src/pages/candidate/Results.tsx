import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { apiError, getMyResults, importProtocols, presentResult } from '../../api/client'
import { DISC_RU } from '../../labels'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'

interface Row {
  id: string; event_name: string; discipline: string; discipline_label: string; status_label: string; place: number
  total_participants: number; is_team: boolean; team_size: number
  event_date: string; protocol_url: string | null; ekp_number?: string | null; trust_level?: string
}

/** A stored protocol link is followed only when it is a web address. */
function protocolHref(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null
  } catch {
    return null
  }
}

/** Competition protocols as a protocol: place first, field size next to it. */
export default function CandidateResults() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState<string | null>(null)
  const [cardError, setCardError] = useState('')
  const { data: rows = [], isLoading, isError, error, refetch } = useQuery<Row[]>({ queryKey: ['myResults'], queryFn: () => getMyResults().then(r => r.data) })
  const [fileNote, setFileNote] = useState('')
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
        lead="Места из официальных протоколов. Разряд присвоен по дисциплине и приходит из реестра, а не за одно соревнование. Протокол соревнования — не цифровой след и не грейд. Работодатель видит год, уровень соревнования и процентиль без названия события." />
      <form className="card mb-6 space-y-2 p-4" onSubmit={e => e.preventDefault()}>
        <label className="field-label" htmlFor="protocol-file">Файл протокола, если реестр молчит</label>
        <input id="protocol-file" type="file" accept=".csv,.txt,.pdf,.xlsx,text/csv,application/pdf" className="text-sm"
          onChange={e => {
            const picked = e.target.files?.[0]
            e.target.value = ''
            if (!picked) return
            setFileNote('')
            void importProtocols(picked).then(r => {
              setFileNote(r.data.added ? `Добавлено строк: ${r.data.added}. Грейд не изменился, в балл они не входят.` : 'Новых строк нет.')
              void refetch()
            }).catch(err => setFileNote(apiError(err, 'Файл не разобран')))
          }} />
        <p className="text-xs text-ink-3">Колонки: дисциплина, дата, место, всего участников. Строка из файла в балл не входит.</p>
        {fileNote && <p className="text-sm text-ink-2" role="status">{fileNote}</p>}
      </form>
      {isLoading && <Skeleton className="h-64" />}
      {isError && <p className="notice-error mb-4" role="alert">{apiError(error, 'Не удалось загрузить протоколы')}</p>}
      {cardError && <p className="notice-error mb-4" role="alert">{cardError}</p>}
      {!isLoading && !isError && rows.length === 0 && (
        <Empty title="Протоколов пока нет">Привяжите ФСП ID в профиле — результаты подтянутся автоматически. Без них категория строится по опросу и тесту.</Empty>
      )}
      {rows.length > 0 && (
        <>
        <ul className="space-y-3 sm:hidden">
          {rows.map(r => {
            const protocol = protocolHref(r.protocol_url)
            return (
              <li key={r.id} className="card space-y-1">
                <p className="text-sm text-ink-3"><span className="place text-base text-ink">{r.place}</span> из {r.total_participants}</p>
                <p className="font-medium text-ink">{r.event_name}{r.trust_level === 'file_import' ? ' · из файла, в балл не входит' : ''}</p>
                <p className="text-sm text-ink-2">{DISC_RU[r.discipline] ?? r.discipline_label}</p>
                <p className="text-xs text-ink-3">{r.status_label}{r.is_team ? `, команда из ${r.team_size}` : ''} · {date(r.event_date)}</p>
                <button type="button" className="inline-flex min-h-9 items-center text-sm font-medium text-accent underline" disabled={busy === r.id} onClick={() => openCard(r.id)}>Краткое удостоверение</button>
                {protocol && <a href={protocol} target="_blank" rel="noreferrer" className="ml-3 inline-flex min-h-9 items-center text-sm text-accent">Протокол</a>}
              </li>
            )
          })}
        </ul>
        <div className="card hidden overflow-x-auto p-0 sm:block" tabIndex={0} role="region" aria-label="Таблица результатов">
          <table className="protocol">
            <thead><tr>
              <th className="w-20 text-right">Место</th><th>Соревнование</th><th>Дисциплина</th><th className="text-right">Дата</th>
            </tr></thead>
            <tbody>
              {rows.map(r => {
                const protocol = protocolHref(r.protocol_url)
                return (
                <tr key={r.id}>
                  <td className="text-right"><span className="place">{r.place}</span><span className="num block text-xs text-ink-3">из {r.total_participants}</span></td>
                  <td>
                    <p className="font-medium text-ink">{r.event_name}{r.trust_level === 'file_import' ? ' · из файла, в балл не входит' : ''}</p>
                    <button type="button" className="mt-0.5 inline-flex min-h-6 items-center text-xs font-medium text-accent underline" disabled={busy === r.id} onClick={() => openCard(r.id)}>Краткое удостоверение</button>
                    <p className="text-xs text-ink-3">{r.status_label}{r.is_team ? `, команда из ${r.team_size}` : ''}{r.ekp_number ? `. ${r.ekp_number.startsWith('ЕКП-демо') ? 'Демо-номер календаря' : 'Номер в календаре ЕКП'}: ${r.ekp_number}` : ''}</p>
                  </td>
                  <td className="text-ink-2">{DISC_RU[r.discipline] ?? r.discipline_label}</td>
                  <td className="num whitespace-nowrap text-right text-ink-2">
                    {date(r.event_date)}
                    {protocol && <a href={protocol} target="_blank" rel="noreferrer" className="ml-1 inline-flex h-6 w-6 items-center justify-center rounded text-accent hover:bg-accent-soft" aria-label="Протокол"><ExternalLink size={14} aria-hidden /></a>}
                  </td>
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  )
}
