import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { apiError, askGuide } from '../api/client'

/** A pointer to a page of this role. The question is not shown back and is not a profile. */
export default function GuideBox({ role }: { role: 'participant' | 'employer' }) {
  const prefix = role === 'participant' ? '/candidate' : '/employer'
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const ask = useMutation({
    mutationFn: () => askGuide(question.trim()).then(r => r.data),
  })
  const links = (ask.data?.links ?? []).filter(link => link.to === prefix || link.to.startsWith(`${prefix}/`))

  return (
    <div className="relative">
      <button type="button" className="btn-nav" aria-expanded={open} onClick={() => setOpen(value => !value)}>Куда нажать</button>
      {open && (
        <form className="absolute right-0 z-20 mt-2 w-72 space-y-2 rounded-lg border border-line bg-panel p-3 shadow-md"
          onSubmit={e => { e.preventDefault(); if (question.trim().length >= 2) ask.mutate() }}>
          <label className="text-xs text-ink-3" htmlFor="guide-q">Вопрос остаётся на сервере</label>
          <input id="guide-q" value={question} onChange={e => setQuestion(e.target.value)} maxLength={200}
            placeholder="Например, где подтвердить грейд" className="input" />
          <button type="submit" className="btn-secondary btn-sm" disabled={question.trim().length < 2 || ask.isPending}>Показать раздел</button>
          {ask.isError && <p className="text-sm text-danger" role="alert">{apiError(ask.error, 'Подсказка не открылась')}</p>}
          {ask.data && (
            <div className="space-y-2 text-sm text-ink">
              <p>{ask.data.answer}</p>
              <ul className="space-y-1">
                {links.map(link => (
                  <li key={link.to}><Link to={link.to} className="text-accent hover:underline" onClick={() => setOpen(false)}>{link.label}</Link></li>
                ))}
              </ul>
            </div>
          )}
        </form>
      )}
    </div>
  )
}
