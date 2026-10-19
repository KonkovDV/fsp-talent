import { useState } from 'react'

import { apiError, industryCase } from '../api/client'

interface Shown {
  label: string
  title: string
  plot: string
  ask: string
  follow: string
}

interface Mark {
  rubric: string
  grade_unchanged: boolean
}

/** A short case for the person's industry, then one follow-up. The grade does not move. */
export default function IndustryCase() {
  const [shown, setShown] = useState<Shown | null>(null)
  const [first, setFirst] = useState('')
  const [follow, setFollow] = useState('')
  const [mark, setMark] = useState<Mark | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    setError('')
    try {
      const { data } = await industryCase()
      if (!data.label || !data.title || !data.plot || !data.ask || !data.follow) return
      setShown({ label: data.label, title: data.title, plot: data.plot, ask: data.ask, follow: data.follow })
      setMark(null)
    } catch (err) {
      setError(apiError(err, 'Кейс не открылся'))
    }
  }

  const check = async () => {
    if (!first.trim() || !follow.trim()) return
    setError('')
    try {
      const { data } = await industryCase({ first: first.trim(), follow: follow.trim() })
      if (!data.rubric) return
      setMark({ rubric: data.rubric, grade_unchanged: data.grade_unchanged })
    } catch (err) {
      setError(apiError(err, 'Ответ не проверился'))
    }
  }

  return (
    <section className="panel mt-6" aria-label="Кейс по отрасли">
      <h2 className="font-semibold">Кейс по отрасли</h2>
      <p className="mt-1 text-sm text-ink-2">Сюжет зависит от отрасли в анкете. Рубрика одна: оба числа. Грейд не меняется.</p>
      {!shown && (
        <button type="button" className="btn-secondary mt-3" onClick={load}>Показать кейс</button>
      )}
      {shown && (
        <div className="mt-3 space-y-2 text-sm">
          <p className="text-ink-2">{shown.label}. {shown.title}.</p>
          <p>{shown.plot}</p>
          <label className="block">{shown.ask}
            <input className="input mt-1" value={first} onChange={e => setFirst(e.target.value)} inputMode="numeric" />
          </label>
          <label className="block">{shown.follow}
            <input className="input mt-1" value={follow} onChange={e => setFollow(e.target.value)} inputMode="numeric" />
          </label>
          <button type="button" className="btn-secondary" disabled={!first.trim() || !follow.trim()} onClick={check}>Проверить</button>
        </div>
      )}
      {mark && <p className="mt-3 text-sm text-ink" role="status">{mark.rubric}. Грейд не изменён.</p>}
      {error && <p className="notice-error mt-3" role="alert">{error}</p>}
    </section>
  )
}
