import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, chooseSlot, downloadInterview, getSlots, proposeSlots, setInterviewOutcome } from '../api/client'

interface Slot {
  id: string
  date: string
  time: string
  format: string
  place: string | null
  chosen: boolean
  outcome: string | null
}

const FORMAT: Record<string, string> = { online: 'онлайн', office: 'в офисе', phone: 'по телефону' }
const OUTCOME: Record<string, string> = { passed: 'прошёл', failed: 'не прошёл', no_show: 'не пришёл' }

/** Times after an accepted invitation. The company offers up to three, the candidate picks one. */
export default function InterviewSlots({ offerId, side, listKey }: {
  offerId: string
  side: 'employer' | 'participant'
  listKey: string
}) {
  const qc = useQueryClient()
  const slots = useQuery({
    queryKey: ['slots', offerId],
    queryFn: () => getSlots(offerId).then(r => r.data as { slots: Slot[]; outcome: string | null }),
  })
  const [draft, setDraft] = useState([{ date: '', time: '', format: 'online', place: '' }])
  const [outcome, setOutcome] = useState('passed')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const rows = slots.data?.slots ?? []
  const chosen = rows.find(row => row.chosen)
  useEffect(() => {
    if (slots.data?.outcome) setOutcome(slots.data.outcome)
  }, [slots.data?.outcome])
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['slots', offerId] })
    qc.invalidateQueries({ queryKey: [listKey] })
  }
  const propose = useMutation({
    mutationFn: () => proposeSlots(offerId, draft.filter(row => row.date && row.time).map(row => ({
      date: row.date, time: row.time, format: row.format, place: row.place || null,
    }))),
    onSuccess: () => { setError(''); setNote('Время отправлено кандидату.'); refresh() },
    onError: e => setError(apiError(e, 'Не удалось предложить время')),
  })
  const choose = useMutation({
    mutationFn: (id: string) => chooseSlot(offerId, id),
    onSuccess: () => { setError(''); setNote('Время выбрано. Календарь можно скачать.'); refresh() },
    onError: e => setError(apiError(e, 'Не удалось выбрать время')),
  })
  const saveOutcome = useMutation({
    mutationFn: () => setInterviewOutcome(offerId, outcome),
    onSuccess: () => { setError(''); setNote('Итог записан.'); refresh() },
    onError: e => setError(apiError(e, 'Не удалось записать итог')),
  })
  const file = useMutation({
    mutationFn: () => downloadInterview(offerId),
    onSuccess: (res) => {
      const url = URL.createObjectURL(res.data)
      const link = document.createElement('a')
      link.href = url
      link.download = 'sobesedovanie.ics'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: e => setError(apiError(e, 'Календарь ещё не готов')),
  })

  return (
    <div className="mt-3 space-y-2 text-sm">
      {rows.length === 0 && side === 'participant' && <p className="text-ink-2">Компания ещё не предложила время.</p>}
      {rows.length > 0 && (
        <ul className="space-y-1">
          {rows.map(row => (
            <li key={row.id} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
              <span className="text-ink">{row.date} {row.time} МСК, {FORMAT[row.format] ?? row.format}{row.place ? `, ${row.place}` : ''}</span>
              {row.chosen && <span className="badge-ok w-max">выбрано</span>}
              {side === 'participant' && !chosen && (
                <button type="button" className="btn-primary btn-sm" disabled={choose.isPending} onClick={() => choose.mutate(row.id)}>Выбрать</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {chosen && (
        <button type="button" className="btn-secondary btn-sm" disabled={file.isPending} onClick={() => file.mutate()}>Скачать календарь</button>
      )}
      {side === 'employer' && !chosen && (
        <form className="flex flex-col gap-2" onSubmit={e => { e.preventDefault(); propose.mutate() }}>
          {draft.map((row, index) => (
            <div key={index} className="flex flex-col gap-2 sm:flex-row">
              <input type="date" required value={row.date} aria-label="Дата" className="input"
                onChange={e => setDraft(draft.map((item, i) => i === index ? { ...item, date: e.target.value } : item))} />
              <input type="time" required value={row.time} aria-label="Время по Москве" className="input"
                onChange={e => setDraft(draft.map((item, i) => i === index ? { ...item, time: e.target.value } : item))} />
              <select value={row.format} aria-label="Формат" className="select"
                onChange={e => setDraft(draft.map((item, i) => i === index ? { ...item, format: e.target.value } : item))}>
                <option value="online">онлайн</option>
                <option value="office">в офисе</option>
                <option value="phone">по телефону</option>
              </select>
              <input value={row.place} placeholder="Ссылка или адрес" aria-label="Ссылка или адрес" className="input"
                onChange={e => setDraft(draft.map((item, i) => i === index ? { ...item, place: e.target.value } : item))} />
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            {draft.length < 3 && (
              <button type="button" className="btn-ghost btn-sm" onClick={() => setDraft([...draft, { date: '', time: '', format: 'online', place: '' }])}>Ещё время</button>
            )}
            <button type="submit" className="btn-primary btn-sm" disabled={propose.isPending}>Предложить время</button>
          </div>
        </form>
      )}
      {side === 'employer' && chosen && (
        <form className="flex flex-col gap-2 sm:flex-row sm:items-center" onSubmit={e => { e.preventDefault(); saveOutcome.mutate() }}>
          <label className="text-ink-2">Итог
            <select value={outcome} aria-label="Итог собеседования" className="select ml-2"
              onChange={e => setOutcome(e.target.value)}>
              <option value="passed">прошёл</option>
              <option value="failed">не прошёл</option>
              <option value="no_show">не пришёл</option>
            </select>
          </label>
          <button type="submit" className="btn-secondary btn-sm" disabled={saveOutcome.isPending}>Записать итог</button>
          {chosen.outcome && <span className="text-ink-2">Сейчас: {OUTCOME[chosen.outcome] ?? chosen.outcome}</span>}
        </form>
      )}
      {side === 'participant' && chosen?.outcome && <p className="text-ink-2">Итог: {OUTCOME[chosen.outcome] ?? chosen.outcome}</p>}
      {note && <p className="notice-info">{note}</p>}
      {error && <p className="notice-error" role="alert">{error}</p>}
    </div>
  )
}
