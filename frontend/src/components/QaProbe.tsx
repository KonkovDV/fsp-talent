import { useState } from 'react'
import { apiError, submitQaProbe } from '../api/client'

/** Up to five input/output pairs. The grade does not move. */
export default function QaProbe() {
  const [rows, setRows] = useState([{ given: '', expected: '' }])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const setCell = (index: number, key: 'given' | 'expected', value: string) => {
    setRows(list => list.map((item, i) => (i === index ? { ...item, [key]: value } : item)))
  }

  const filled = rows.filter(row => row.given.trim() && row.expected.trim())

  const submit = async () => {
    setBusy(true)
    setNote('')
    try {
      const { data } = await submitQaProbe(filled)
      const caught = data.killed.length ? data.killed.join(', ') : 'пока ни одного'
      setNote(`Принято пар: ${data.accepted}. Отклонено: ${data.rejected}. Пойманы дефекты: ${caught}. Грейд не изменился.`)
    } catch (err) {
      setNote(apiError(err, 'Проверка не прошла'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card space-y-3" onSubmit={event => { event.preventDefault(); void submit() }}>
      <h2 className="section-title">Практическая проверка QA</h2>
      <p className="text-sm text-ink-2">
        Функция держит целое число в границах от 0 до 100. Напишите до пяти пар «вход — ожидаемый результат».
        Пара проверяется на исправной программе и на копиях с внесёнными дефектами. Грейд от этого не меняется.
      </p>
      {rows.map((row, index) => (
        <div key={index} className="flex gap-2">
          <input className="input" aria-label={`Вход ${index + 1}`} inputMode="numeric" value={row.given}
            onChange={event => setCell(index, 'given', event.target.value)} />
          <input className="input" aria-label={`Ожидание ${index + 1}`} inputMode="numeric" value={row.expected}
            onChange={event => setCell(index, 'expected', event.target.value)} />
        </div>
      ))}
      <div className="flex flex-wrap gap-3">
        {rows.length < 5 && (
          <button type="button" className="btn-ghost" onClick={() => setRows(list => [...list, { given: '', expected: '' }])}>
            Ещё пара
          </button>
        )}
        <button type="submit" className="btn-secondary" disabled={busy || filled.length === 0}>Проверить пары</button>
      </div>
      {note && <p className="text-sm text-ink-2" role="status">{note}</p>}
    </form>
  )
}
