import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiError, forgotPassword, publicDemo, resetPassword, type Role } from '../api/client'
import { useAuthStore } from '../store/authStore'
import AuthShell from '../components/AuthShell'
import { passwordRule } from '../passwordRule'

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
  const [mailConsole, setMailConsole] = useState(false)

  useEffect(() => {
    publicDemo()
      .then(res => setMailConsole(Boolean(res.data.demo_mode && res.data.mail_console)))
      .catch(() => setMailConsole(false))
  }, [])

  const request = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true)
    try { await forgotPassword(email, role); setSent(true) } catch (err) { setError(apiError(err)) } finally { setBusy(false) }
  }
  const reset = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const { data } = await resetPassword({ email, role, code, new_password: password })
      setAuth(data.access_token, role)
      navigate(role === 'employer' ? '/employer' : '/candidate', { replace: true })
    } catch (err) { setError(apiError(err, 'Код не подошёл')) } finally { setBusy(false) }
  }

  if (mailConsole) {
    return (
      <AuthShell title="Сброс пароля" lead="На демо-стенде письма не отправляются, используйте демо-аккаунты."
        aside={<Link to={`/login?role=${role}`} className="hover:text-accent">Ко входу</Link>}>
        <p className="notice-info" role="status">На демо-стенде письма не отправляются, используйте демо-аккаунты.</p>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Сброс пароля" lead="Пришлём код на email, затем зададите новый пароль."
      aside={<Link to={`/login?role=${role}`} className="hover:text-accent">Ко входу</Link>}>
      {!sent ? (
        <form onSubmit={request} className="space-y-4">
          <div><label className="field-label" htmlFor="email">Email</label>
            <input id="email" value={email} onChange={e => setEmail(e.target.value)} type="email" className="input" /></div>
          <button disabled={busy || !email} className="btn-primary w-full py-3">Прислать код</button>
        </form>
      ) : (
        <form onSubmit={reset} className="space-y-4">
          <p className="text-sm text-ink-2">Если аккаунт с адресом {email} есть, код уже в почте.</p>
          <div><label className="field-label" htmlFor="code">Код из письма</label>
            <input id="code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric"
              aria-label="Код из письма" className="input font-display tracking-[0.3em]" /></div>
          <div><label className="field-label" htmlFor="np">Новый пароль</label>
            <input id="np" value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete="new-password"
              aria-label="Новый пароль" className="input" /><p className="field-hint">Не короче 8 символов, не длиннее 72 байт (кириллица: до 36 букв).</p></div>
          <button disabled={busy || code.length !== 6 || !passwordRule.safeParse(password).success} className="btn-primary w-full py-3">Сменить пароль</button>
        </form>
      )}
      {error && <p className="notice-error mt-4" role="alert">{error}</p>}
    </AuthShell>
  )
}
