import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { apiError, askGuardian } from '../api/client'

/** A candidate aged 15–17 names a legal representative; the card enters search after the guardian confirms. */
export default function GuardianCard({ sentTo }: { sentTo: string | null }) {
  const qc = useQueryClient()
  const [email, setEmail] = useState(sentTo ?? '')
  const [note, setNote] = useState('')
  const send = useMutation({
    mutationFn: () => askGuardian(email.trim()),
    onSuccess: () => { setNote('Письмо отправлено. Карточка появится в поиске, когда представитель подтвердит согласие.'); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: (e: unknown) => setNote(apiError(e)),
  })
  return (
    <section className="card space-y-3" aria-labelledby="guardian-title" data-testid="guardian">
      <div className="flex items-start gap-3">
        <ShieldCheck className="mt-0.5 shrink-0 text-accent" size={20} aria-hidden />
        <div>
          <h2 id="guardian-title" className="section-title">Согласие родителя или законного представителя</h2>
          <p className="text-sm text-ink-2">Вам меньше 18 лет, поэтому работодатели увидят карточку только после согласия представителя (ч. 6 ст. 9 152-ФЗ). Тест и задания доступны уже сейчас.</p>
        </div>
      </div>
      <form className="flex flex-wrap items-end gap-2" onSubmit={e => { e.preventDefault(); send.mutate() }}>
        <label className="min-w-0 flex-1 basis-60 text-sm">Email представителя
          <input type="email" required value={email} onChange={e => setEmail(e.target.value)} className="input mt-1" autoComplete="off" />
        </label>
        <button type="submit" className="btn-primary" disabled={!email.includes('@') || send.isPending}>{sentTo ? 'Отправить ещё раз' : 'Отправить запрос'}</button>
      </form>
      {(note || sentTo) && <p className="text-sm text-ink-2" role="status">{note || `Запрос отправлен на ${sentTo}. Ждём подтверждения.`}</p>}
    </section>
  )
}
