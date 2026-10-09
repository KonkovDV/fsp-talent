import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { MailCheck } from 'lucide-react'
import { apiError, resendVerification, verifyEmail, type Role } from '../api/client'
import { useAuthStore } from '../store/authStore'
import AuthShell from '../components/AuthShell'
import { dropLetterToken, forgetLetterToken, letterToken, onceLetter } from '../lib/letterToken'

/** Email confirmation: 6-digit code from the letter, or the link (#token=…) that fills it in. */
export default function VerifyPage() {
  const [params] = useSearchParams()
  const email = params.get('email') ?? ''
  const role: Role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const [token] = useState(letterToken)
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const location = useLocation()
  const [resentCode, setDemoCode] = useState<string | null>(null)
  const demoCode = resentCode ?? (location.state as { demoCode?: string } | null)?.demoCode ?? null
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(60)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const finish = (data: { access_token: string; role: Role }) => {
    setAuth(data.access_token, data.role)
    navigate(data.role === 'employer' ? '/employer' : '/candidate?welcome=1', { replace: true })
  }

  useEffect(() => {
    if (!token) return
    dropLetterToken()
    const job = onceLetter(token, () => verifyEmail({ token }).then(r => r.data))
    if (!job) return
    setBusy(true)
    job.then(data => { forgetLetterToken(); finish(data) })
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
    try {
      const r = await resendVerification(email, role)
      if (r.data?.demo_code) setDemoCode(r.data.demo_code)
      setCooldown(60)
    }
    catch (err) { setError(apiError(err)) }
  }

  return (
    <AuthShell title="Подтвердите email"
      lead={email ? <>Код отправлен на <b className="text-ink">{email}</b>. Он действует 30 минут; можно просто открыть ссылку из письма.</> : 'Откройте ссылку из письма или введите код.'}
      aside={<Link to={`/login?role=${role}`} className="hover:text-accent">Ко входу</Link>}>
      <div className="flex items-center gap-3 pb-5"><MailCheck className="text-accent" size={22} aria-hidden />
        <span className="text-sm text-ink-2">Шесть цифр из письма</span></div>
      {demoCode && (
        <p className="notice-info mb-4" role="status">
          <span>Демо-стенд: письма отсюда не уходят. Ваш код — <b className="font-mono tracking-widest">{demoCode}</b></span>
        </p>
      )}
      {token && busy ? <p className="text-sm text-ink-2">Проверяем ссылку…</p> : (
        <>
          <form onSubmit={submit} className="space-y-3">
            <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              inputMode="numeric" autoComplete="one-time-code" placeholder="••••••" aria-label="Код из письма"
              className="input py-3 text-center font-display text-3xl tracking-[0.4em]" />
            <button type="submit" disabled={busy || code.length !== 6 || !email} className="btn-primary w-full py-3">
              {busy ? 'Проверяем…' : 'Подтвердить'}
            </button>
          </form>
          {email && (
            <button onClick={resend} disabled={cooldown > 0} className="mt-4 text-sm text-accent disabled:text-ink-3">
              {cooldown > 0 ? `Отправить код ещё раз через ${cooldown} с` : 'Отправить код ещё раз'}
            </button>
          )}
        </>
      )}
      {error && <p className="notice-error mt-4" role="alert">{error}</p>}
    </AuthShell>
  )
}
