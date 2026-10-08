import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiError, apiErrorCode, changePassword, downloadMyData } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { passwordRule } from '../passwordRule'

/** Download this account's own data, and replace the password without leaving the cabinet. */
export default function AccountSecurity() {
  const setAuth = useAuthStore(s => s.setAuth)
  const role = useAuthStore(s => s.userRole)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [note, setNote] = useState('')
  const [guard, setGuard] = useState('')
  const [error, setError] = useState('')

  const download = useMutation({
    mutationFn: () => downloadMyData().then(r => r.data as Blob),
    onSuccess: blob => {
      setError('')
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = role === 'employer' ? 'dannye-kompanii.json' : 'moi-dannye.json'
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: e => setError(apiError(e, 'Не удалось скачать данные')),
  })

  const save = useMutation({
    mutationFn: () => changePassword(current, next).then(r => r.data as { access_token: string; role: 'participant' | 'employer' }),
    onSuccess: data => {
      setAuth(data.access_token, data.role)
      setCurrent(''); setNext(''); setAgain('')
      setError('')
      setNote('Пароль изменён. Другие сеансы этого аккаунта закрыты.')
    },
    onError: e => {
      setNote('')
      if (apiErrorCode(e) === 'demo_protected') {
        setError('')
        setGuard(apiError(e))
        return
      }
      setGuard('')
      setError(apiError(e, 'Пароль не изменён'))
    },
  })

  const mismatch = next !== '' && again !== '' && next !== again
  const ready = current.length > 0 && passwordRule.safeParse(next).success && next === again && next !== current

  return (
    <section className="card space-y-4" aria-labelledby="account-security-title">
      <h2 id="account-security-title" className="section-title">Данные и пароль</h2>
      <p className="text-sm text-ink-2">Файл содержит только ваши данные: профиль, согласия и приглашения. Пароль и ключи заданий в него не входят.</p>
      <button type="button" className="btn-secondary btn-sm" disabled={download.isPending} onClick={() => download.mutate()}>
        {download.isPending ? 'Готовим файл…' : 'Скачать мои данные'}
      </button>
      <form className="space-y-3" onSubmit={e => { e.preventDefault(); if (ready) save.mutate() }}>
        <div>
          <label className="field-label" htmlFor="pw-current">Текущий пароль</label>
          <input id="pw-current" type="password" autoComplete="current-password" className="input" value={current} onChange={e => setCurrent(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="pw-next">Новый пароль</label>
          <input id="pw-next" type="password" autoComplete="new-password" className="input" value={next} onChange={e => setNext(e.target.value)} />
        </div>
        <div>
          <label className="field-label" htmlFor="pw-again">Новый пароль ещё раз</label>
          <input id="pw-again" type="password" autoComplete="new-password" className="input" value={again} onChange={e => setAgain(e.target.value)} />
        </div>
        {mismatch && <p className="field-error" role="alert">Пароли не совпадают</p>}
        {guard && <p className="text-sm text-ink-2" role="status">{guard}</p>}
        {error && <p className="field-error" role="alert">{error}</p>}
        {note && <p className="text-sm text-ok" role="status">{note}</p>}
        <button type="submit" className="btn-primary btn-sm" disabled={!ready || save.isPending}>
          {save.isPending ? 'Сохраняем…' : 'Сменить пароль'}
        </button>
      </form>
    </section>
  )
}
