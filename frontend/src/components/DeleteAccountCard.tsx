import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiError, apiErrorCode, deleteMyAccount, signOut } from '../api/client'

/** 152-FZ, art. 21: the person can erase the account. Typing the word protects against a stray click. */
export default function DeleteAccountCard() {
  const [open, setOpen] = useState(false)
  const [word, setWord] = useState('')
  const navigate = useNavigate()
  const erase = useMutation({
    mutationFn: () => deleteMyAccount(word).then(r => r.data),
    onSuccess: () => { void signOut().then(() => navigate('/', { replace: true })) },
  })
  return (
    <div className="card space-y-3">
      <h2 className="section-title">Удаление аккаунта</h2>
      <p className="text-sm text-ink-2">
        Удалим имя, контакты, навыки и привязку ФСП, отзовём ожидающие приглашения. Результаты соревнований
        останутся в протоколе без связи с вами. Отменить удаление нельзя.
      </p>
      {!open
        ? <button type="button" onClick={() => setOpen(true)} className="btn-secondary btn-sm">Удалить аккаунт</button>
        : (
          <form className="space-y-2" onSubmit={e => { e.preventDefault(); erase.mutate() }}>
            <label className="field-label" htmlFor="delete-word">Введите слово «удалить»</label>
            <input id="delete-word" value={word} onChange={e => setWord(e.target.value)} className="input" autoComplete="off" />
            {erase.isError && apiErrorCode(erase.error) === 'demo_protected'
              ? <p className="text-sm text-ink-2" role="status">{apiError(erase.error)}</p>
              : erase.isError && <p className="field-error" role="alert">{apiError(erase.error)}</p>}
            <div className="flex gap-2">
              <button type="submit" disabled={word.trim().toLowerCase() !== 'удалить' || erase.isPending} className="btn-danger btn-sm">
                {erase.isPending ? 'Удаляем…' : 'Удалить навсегда'}
              </button>
              <button type="button" onClick={() => { setOpen(false); setWord('') }} className="btn-ghost btn-sm">Отмена</button>
            </div>
          </form>
        )}
    </div>
  )
}
