import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiError, designProbe } from '../api/client'

const SEED = 'layout-seed'

/** Contrast and geometry of one layout. The grade does not move. */
export default function DesignProbe() {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const puzzle = useQuery({
    queryKey: ['design-probe', SEED],
    enabled: open,
    queryFn: () => designProbe(SEED).then(response => response.data),
  })

  const pick = async (choice: string) => {
    setBusy(true)
    setNote('')
    try {
      const { data } = await designProbe(SEED, choice)
      setNote(data.matched
        ? 'Пометка совпала с расчётом. Грейд не изменился.'
        : 'Пометка не совпала с расчётом. Грейд не изменился.')
    } catch (err) {
      setNote(apiError(err, 'Проверка не прошла'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card space-y-3">
      <h2 className="section-title">Макет с дефектом</h2>
      <p className="text-sm text-ink-2">
        Цвета и прямоугольники заданы числами. Пометка выбирается по контрасту и по положению фигур, не по вкусу.
        Грейд от этого не меняется.
      </p>
      {!open && (
        <button type="button" className="btn-secondary" onClick={() => setOpen(true)}>Показать макет</button>
      )}
      {puzzle.data?.lines && (
        <ul className="text-sm text-ink">
          {puzzle.data.lines.map(line => <li key={line}>{line}</li>)}
        </ul>
      )}
      {puzzle.data?.choices && (
        <div className="flex flex-wrap gap-2">
          {puzzle.data.choices.map(choice => (
            <button key={choice} type="button" className="btn-ghost" disabled={busy} onClick={() => void pick(choice)}>
              {choice}
            </button>
          ))}
        </div>
      )}
      {note && <p className="text-sm text-ink-2" role="status">{note}</p>}
    </section>
  )
}
