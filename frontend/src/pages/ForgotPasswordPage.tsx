import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiError, forgotPassword, resetPassword, type Role } from '../api/client'
import { useAuthStore } from '../store/authStore'

export default function ForgotPasswordPage() {
  const [params] = useSearchParams()
  const role: Role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [sent, setSent] = useState(false)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const request = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true)
    try { await forgotPassword(email, role); setSent(true) } catch (err) { setError(apiError(err)) } finally { setBusy(false) }
  }
  const reset = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const { data } = await resetPassword({ email, role, code, new_password: password })
      setAuth(data.access_token, data.refresh_token, role)
      navigate(role === 'employer' ? '/employer' : '/candidate', { replace: true })
    } catch (err) { setError(apiError(err, 'Код не подошёл')) } finally { setBusy(false) }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center bg-surface-0 px-4">
      <div className="card w-full max-w-md space-y-4">
        <h1 className="text-2xl font-bold">Сброс пароля</h1>
        {!sent ? (
          <form onSubmit={request} className="space-y-3">
            <label className="block text-sm">Email<input value={email} onChange={e => setEmail(e.target.value)} type="email" className="mt-1 input" /></label>
            <button disabled={busy || !email} className="btn-primary w-full">Прислать код</button>
          </form>
        ) : (
          <form onSubmit={reset} className="space-y-3">
            <p className="text-sm text-text-secondary">Если аккаунт с адресом {email} есть, мы отправили на него код.</p>
            <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
              placeholder="Код из письма" aria-label="Код из письма" className="input font-mono" />
            <input value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete="new-password"
              placeholder="Новый пароль, от 8 символов" aria-label="Новый пароль" className="input" />
            <button disabled={busy || code.length !== 6 || password.length < 8} className="btn-primary w-full">Сменить пароль</button>
          </form>
        )}
        {error && <p className="text-fsp-red text-sm bg-red-50 rounded-lg px-4 py-2" role="alert">{error}</p>}
        <p className="text-sm text-text-muted"><Link to={`/login?role=${role}`} className="hover:underline">Ко входу</Link></p>
      </div>
    </div>
  )
}
