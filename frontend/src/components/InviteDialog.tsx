import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { apiError, createOffer } from '../api/client'
import Modal from './Modal'

/** The invitation: role, salary range in roubles (mandatory, TZ 2.2), format and how to reach the employer. */
export default function InviteDialog({ candidateId, defaultRole = '', onClose, onSent }: {
  candidateId: string; defaultRole?: string; onClose: () => void; onSent?: () => void
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    role: defaultRole, salary_from_gross: 150_000, salary_to_gross: 250_000, work_format: 'remote', message: '', contact_method: '',
  })
  const [error, setError] = useState('')

  const send = useMutation({
    mutationFn: () => createOffer({ ...form, candidate_id: candidateId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['employerOffers'] }); onSent?.(); onClose() },
    onError: e => setError(apiError(e, 'Приглашение не отправлено')),
  })
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (form.role.trim().length < 2) return setError('Укажите должность')
    if (form.salary_from_gross <= 0 || form.salary_to_gross < form.salary_from_gross) return setError('Зарплата «до» должна быть не меньше «от»')
    if (form.contact_method.trim().length < 3) return setError('Укажите, как кандидату связаться с вами')
    setError('')
    send.mutate()
  }
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: k.startsWith('salary') ? Number(e.target.value) : e.target.value })

  return (
    <Modal titleId="invite-title" onClose={onClose} sheet>
      <form onSubmit={submit} className="w-full animate-rise rounded-t-xl border border-line bg-panel p-6 shadow-pop sm:rounded-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="invite-title" className="font-display text-lg font-bold text-ink">Приглашение кандидату</h2>
            <p className="mt-1 text-sm text-ink-2">Кандидат увидит компанию, должность и зарплату. Его контакты откроются, если он примет приглашение.</p>
          </div>
          <button type="button" onClick={onClose} className="btn-ghost h-8 w-8 p-0" aria-label="Закрыть"><X size={18} /></button>
        </div>
        <div className="mt-5 space-y-4">
          <div><label className="field-label" htmlFor="inv-role">Должность</label>
            <input id="inv-role" value={form.role} onChange={set('role')} className="input" placeholder="Backend-разработчик" autoFocus /></div>
          <fieldset>
            <legend className="field-label">Зарплата до вычета НДФЛ, ₽ в месяц</legend>
            <div className="grid grid-cols-2 gap-3">
              <input type="number" min={0} step={5000} value={form.salary_from_gross} onChange={set('salary_from_gross')} className="input num" aria-label="От" />
              <input type="number" min={0} step={5000} value={form.salary_to_gross} onChange={set('salary_to_gross')} className="input num" aria-label="До" />
            </div>
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><label className="field-label" htmlFor="inv-format">Формат</label>
              <select id="inv-format" value={form.work_format} onChange={set('work_format')} className="select">
                <option value="remote">удалённо</option><option value="hybrid">гибрид</option><option value="office">в офисе</option>
              </select></div>
            <div><label className="field-label" htmlFor="inv-contact">Как связаться с вами</label>
              <input id="inv-contact" value={form.contact_method} onChange={set('contact_method')} className="input" placeholder="Telegram или email" /></div>
          </div>
          <div><label className="field-label" htmlFor="inv-msg">Сообщение, если нужно</label>
            <textarea id="inv-msg" value={form.message} onChange={set('message')} rows={3} className="input resize-none"
              placeholder="Чем будет заниматься, почему пишем именно ему" /></div>
        </div>
        {error && <p className="notice-error mt-4" role="alert">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-secondary">Отмена</button>
          <button type="submit" disabled={send.isPending} className="btn-invite">{send.isPending ? 'Отправляем…' : 'Отправить приглашение'}</button>
        </div>
      </form>
    </Modal>
  )
}
