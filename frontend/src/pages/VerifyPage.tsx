import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { MailCheck } from 'lucide-react'
import { apiError, resendVerification, verifyEmail, type Role } from '../api/client'
import { useAuthStore } from '../store/authStore'

/** Email confirmation: 6-digit code from the letter, or the link (?token=…) that fills it in. */
export default function VerifyPage() {
  const [params] = useSearchParams()
  const email = params.get('email') ?? ''
  const role: Role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const token = params.get('token')
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(60)
  const tried = useRef(false)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const finish = (data: { access_token: string; refresh_token: string; role: Role }) => {
    setAuth(data.access_token, data.refresh_token, data.role)
    navigate(data.role === 'employer' ? '/employer' : '/candidate?welcome=1', { replace: true })
  }

  useEffect(() => {
    if (!token || tried.current) return
    tried.current = true
    setBusy(true)
    verifyEmail({ token }).then(r => finish(r.data))
      .catch(e => setError(apiError(e, 'Ссылка не подошла. Введите код из письма.')))
      .finally(() => setBusy(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setBusy(true)
    try { finish((await verifyEmail({ email, code, role })).data) }
    catch (err) { setError(apiError(err, 'Код не подошёл')) }
    finally { setBusy(false) }
  }
  const resend = async () => {
    setError('')
    try { await resendVerification(email, role); setCooldown(60) }
    catch (err) { setError(apiError(err)) }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center bg-surface-0 px-4">
      <div className="card w-full max-w-md space-y-4">
        <MailCheck className="text-fsp-violet" size={32} />
        <h1 className="text-2xl font-bold">Подтвердите email</h1>
        {token && busy ? <p className="text-sm text-text-muted">Проверяем ссылку…</p> : (
          <>
            <p className="text-sm text-text-secondary">
              {email ? <>Мы отправили код на <b>{email}</b>. </> : null}
              Код действует 30 минут. Можно просто открыть ссылку из письма.
            </p>
            <form onSubmit={submit} className="space-y-3">
              <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                inputMode="numeric" autoComplete="one-time-code" placeholder="000000" aria-label="Код из письма"
                className="input text-center text-2xl tracking-[0.5em] font-mono" />
              <button type="submit" disabled={busy || code.length !== 6 || !email} className="btn-primary w-full">
                {busy ? 'Проверяем…' : 'Подтвердить'}
              </button>
            </form>
            {email && (
              <button onClick={resend} disabled={cooldown > 0} className="text-sm text-fsp-violet disabled:text-text-muted">
                {cooldown > 0 ? `Отправить код ещё раз через ${cooldown} с` : 'Отправить код ещё раз'}
              </button>
            )}
          </>
        )}
        {error && <p className="text-fsp-red text-sm bg-red-50 rounded-lg px-4 py-2" role="alert">{error}</p>}
        <p className="text-sm text-text-muted"><Link to={`/login?role=${role}`} className="hover:underline">Ко входу</Link></p>
      </div>
    </div>
  )
}
