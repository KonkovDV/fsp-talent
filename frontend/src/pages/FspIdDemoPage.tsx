import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { apiError, fspDemoLogin } from '../api/client'

const PARAMS = ['client_id', 'redirect_uri', 'state', 'code_challenge', 'code_challenge_method'] as const

/**
 * Stand-in for the FSP ID login page (Keycloak in production). It receives the usual OIDC authorization
 * request, checks the demo registry and sends the browser back to the platform with a one-time code.
 * The page looks deliberately different from the platform: it belongs to the identity provider.
 */
export default function FspIdDemoPage() {
  const [params] = useSearchParams()
  const [fspId, setFspId] = useState('FSP2007')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const request = Object.fromEntries(PARAMS.map(k => [k, params.get(k) ?? '']))
  const valid = PARAMS.every(k => request[k]) && params.get('response_type') === 'code'

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const { data } = await fspDemoLogin({ ...request, fsp_id: fspId, password })
      window.location.assign(data.redirect_to)
    } catch (err) {
      setError(apiError(err, 'Вход не выполнен'))
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-sunken px-4 py-10">
      <div className="w-full max-w-sm">
        <p className="mb-3 rounded-md border border-warn/40 bg-warn-soft px-3 py-2 text-xs text-ink" role="note">
          Демо-провайдер ФСП ID. В работающей интеграции здесь откроется страница входа Keycloak Федерации,
          протокол обмена тот же: OpenID Connect, код и PKCE.
        </p>
        <div className="rounded-xl border border-line bg-panel p-6 shadow-sm">
          <div className="flex items-center gap-2 text-ink">
            <ShieldCheck size={22} className="text-accent" aria-hidden />
            <h1 className="font-display text-lg font-bold">ФСП ID</h1>
          </div>
          {!valid
            ? <p className="mt-4 text-sm text-ink-2">Запрос на вход неполный. Начните привязку из профиля на платформе.</p>
            : <>
                <p className="mt-2 text-sm text-ink-2">
                  Приложение <b className="text-ink">«ФСП Талант»</b> просит подтвердить ваш ФСП ID и получить
                  результаты соревнований из протоколов.
                </p>
                <form onSubmit={submit} className="mt-5 space-y-3">
                  <label className="block">
                    <span className="field-label">ФСП ID</span>
                    <input className="input" value={fspId} onChange={e => setFspId(e.target.value)} autoComplete="username" />
                  </label>
                  <label className="block">
                    <span className="field-label">Пароль</span>
                    <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
                  </label>
                  <button type="submit" className="btn-primary w-full" disabled={busy || !fspId || !password}>
                    {busy ? 'Входим…' : 'Войти и разрешить'}
                  </button>
                </form>
                <p className="mt-4 text-xs text-ink-3">Демо-реестр: FSP2000–FSP2099, пароль test.</p>
              </>}
          {error && <p className="notice-error mt-4" role="alert">{error}</p>}
        </div>
      </div>
    </div>
  )
}
