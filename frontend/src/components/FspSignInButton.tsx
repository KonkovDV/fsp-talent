import { useState } from 'react'
import { apiError, fspSignInAuthorize } from '../api/client'

/**
 * «Войти через ФСП ID»: the Federation's single entry point (OIDC code flow + PKCE). The FSP password is
 * typed only on the provider's page; email registration stays as the other way in.
 */
export default function FspSignInButton({ label = 'Войти через ФСП ID' }: { label?: string }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const start = async () => {
    setBusy(true); setError('')
    try {
      const { data } = await fspSignInAuthorize()
      window.location.assign(data.authorize_url)
    } catch (e) {
      setError(apiError(e, 'ФСП ID сейчас недоступен'))
      setBusy(false)
    }
  }
  return (
    <div>
      <button type="button" onClick={start} disabled={busy} data-testid="fsp-signin"
        className="btn w-full gap-2.5 border border-line-strong bg-panel py-3 text-ink hover:border-accent hover:text-accent">
        <svg width={18} height={18} viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="7" fill="#402FFF" /><path d="M8.5 10h15M16 10v13" stroke="#fff" strokeWidth="3.4" fill="none" strokeLinecap="round" /><circle cx="23" cy="22" r="3" fill="#EC1D35" /></svg>
        {busy ? 'Переходим в ФСП ID…' : label}
      </button>
      {error && <p className="notice-error mt-3" role="alert">{error}</p>}
    </div>
  )
}

export function OrDivider() {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-ink-3" aria-hidden>
      <span className="h-px flex-1 bg-line" />или по email<span className="h-px flex-1 bg-line" />
    </div>
  )
}
