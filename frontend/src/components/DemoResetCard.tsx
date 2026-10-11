import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiError, resetMyDemo } from '../api/client'

/** Демо-стенд, аккаунты jury1–jury10: следующий эксперт начинает с чистого кабинета (DoR-04). */
export default function DemoResetCard() {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  return (
    <section className="card flex flex-wrap items-center justify-between gap-3" aria-label="Демо-режим" data-testid="demo-reset">
      <p className="text-sm text-ink-2">Демо-аккаунт жюри. Перед следующим проверяющим можно начать заново: опрос, тест, грейд и приглашения очистятся, пароль останется.</p>
      <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={() => {
        if (!window.confirm('Начать заново? Опрос, результаты теста и приглашения этого демо-аккаунта будут удалены.')) return
        setBusy(true)
        setNote('')
        void resetMyDemo()
          .then(() => { setNote('Готово: кабинет как новый.'); return qc.invalidateQueries() })
          .catch(error => setNote(apiError(error, 'Сброс не удался')))
          .finally(() => setBusy(false))
      }}>Начать заново (демо)</button>
      {note && <p className="w-full text-sm text-ink" role="status">{note}</p>}
    </section>
  )
}
