import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiError, fspSignInCallback, fspSignUp, legalDocuments } from '../api/client'
import AuthShell from '../components/AuthShell'
import { ConsentChecklist, requiredKinds } from '../components/LegalConsents'
import { useAuthStore } from '../store/authStore'

interface NeedsConsent { ticket: string; fsp_id: string; display_name: string | null; region: string | null; results: number }

/**
 * Return from FSP ID at sign-in. A linked account goes straight to the cabinet. A new person sees the data
 * the FSP registry has and accepts the required documents; only then the account is created (152-FZ).
 */
export default function FspSignInCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [pending, setPending] = useState<NeedsConsent | null>(null)
  const [error, setError] = useState('')
  const [consents, setConsents] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const sent = useRef(false)
  const { data: docs } = useQuery({ queryKey: ['legal-list', 'participant'], queryFn: () => legalDocuments('participant').then(r => r.data) })
  const missing = requiredKinds(docs).filter(k => !consents.includes(k))

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    const code = params.get('code'), state = params.get('state')
    if (!code || !state) { setError('В ответе ФСП ID нет кода. Начните вход заново.'); return }
    fspSignInCallback(code, state)
      .then(({ data }) => {
        if (data.status === 'signed_in') {
          setAuth(data.access_token, data.refresh_token, 'participant')
          navigate('/candidate', { replace: true })
        } else setPending(data as NeedsConsent)
      })
      .catch(e => setError(apiError(e, 'Вход через ФСП ID не удался')))
  }, [params, navigate, setAuth])

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!pending || missing.length) return
    setBusy(true); setError('')
    try {
      const { data } = await fspSignUp(pending.ticket, consents)
      setAuth(data.access_token, data.refresh_token, 'participant')
      navigate('/candidate', { replace: true })
    } catch (err) {
      setError(apiError(err, 'Аккаунт не создан'))
      setBusy(false)
    }
  }

  return (
    <AuthShell title={pending ? 'Новый аккаунт через ФСП ID' : 'Вход через ФСП ID'}
      lead={pending ? 'ФСП ID подтвердил вашу личность. Аккаунта на платформе ещё нет: примите документы, и мы создадим его по данным реестра ФСП.' : undefined}
      aside={<Link to="/login" className="text-accent hover:underline">Вернуться ко входу</Link>}>
      {!pending && !error && <p className="text-sm text-ink-2" role="status">Проверяем ответ ФСП ID…</p>}
      {pending && (
        <form onSubmit={create} className="space-y-5">
          <dl className="panel-quiet grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-ink-3">ФСП ID</dt><dd className="font-mono text-ink">{pending.fsp_id}</dd>
            {pending.display_name && <><dt className="text-ink-3">Имя</dt><dd className="text-ink">{pending.display_name}</dd></>}
            {pending.region && <><dt className="text-ink-3">Регион</dt><dd className="text-ink">{pending.region}</dd></>}
            <dt className="text-ink-3">Протоколов</dt><dd className="num text-ink">{pending.results}</dd>
          </dl>
          <ConsentChecklist role="participant" value={consents} onChange={setConsents} />
          <p className="text-xs text-ink-3">Входить вы будете через ФСП ID, пароль на платформе не нужен. Email не обязателен:
            для связи с работодателем добавьте Telegram или телефон в профиле. Их увидит только компания, чьё приглашение вы примете.</p>
          <button type="submit" disabled={busy || missing.length > 0} className="btn-primary w-full py-3">
            {busy ? 'Создаём…' : 'Создать аккаунт и войти'}
          </button>
        </form>
      )}
      {error && <p className="notice-error mt-4" role="alert">{error}</p>}
    </AuthShell>
  )
}
