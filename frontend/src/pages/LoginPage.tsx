import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../store/authStore'
import { apiError, apiErrorCode, loginEmployer, loginParticipant, publicDemo, publicJuryFree } from '../api/client'
import { serverUnreachable } from '../demoFallback'
import AuthShell, { RoleSwitch } from '../components/AuthShell'
import FspSignInButton, { OrDivider } from '../components/FspSignInButton'

const schema = z.object({
  username: z.string().email('Введите email'),
  password: z.string().min(1, 'Введите пароль'),
})
type Form = z.infer<typeof schema>

/** Same-site relative path only: starts with «/», not «//», no «:». */
export function safeNextPath(raw: string | null): string | null {
  if (!raw) return null
  if (!raw.startsWith('/') || raw.startsWith('//') || raw.includes(':')) return null
  return raw
}


const DEMO = {
  participant: [['fsp001@demo.talent', 'с историей ФСП'], ['nofsp@demo.talent', 'без ФСП']],
  employer: [['hr@sibcode.demo', '«Сибирский код»']],
}

export default function LoginPage() {
  const [params] = useSearchParams()
  const role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const enterExample = useAuthStore(s => s.enterExample)
  const [error, setError] = useState('')
  const [demo, setDemo] = useState(false)
  const [offline, setOffline] = useState(false)
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) })

  useEffect(() => {
    publicDemo().then(res => setDemo(Boolean(res.data.demo_mode))).catch((e: unknown) => {
      setDemo(false)
      if (serverUnreachable(e)) setOffline(true)
    })
  }, [])

  const takeJury = async () => {
    try {
      const email = (await publicJuryFree()).data.email
      if (/^jury([1-9]|10)@demo\.talent$/.test(email)) {
        setValue('username', email)
        setValue('password', 'demo12345')
        return
      }
    } catch {
      // The stand did not answer. A random account is still a way in.
    }
    const n = 1 + Math.floor(Math.random() * 10)
    setValue('username', `jury${n}@demo.talent`)
    setValue('password', 'demo12345')
  }

  const onSubmit = async ({ username, password }: Form) => {
    setError('')
    try {
      const res = role === 'participant' ? await loginParticipant(username, password) : await loginEmployer(username, password)
      setAuth(res.data.access_token, role)
      const next = safeNextPath(params.get('next'))
      navigate(next ?? (role === 'participant' ? '/candidate' : '/employer'))
    } catch (e: unknown) {
      if (apiErrorCode(e) === 'email_not_verified') {
        navigate(`/verify?email=${encodeURIComponent(username.trim().toLowerCase())}&role=${role}`)
        return
      }
      setError(apiError(e, 'Не удалось войти'))
    }
  }

  return (
    <AuthShell title="Вход" lead={role === 'participant' ? 'Кабинет кандидата: категория, тест, приглашения.' : 'Кабинет работодателя: потребности, подборка, приглашения.'}
      aside={<>Нет аккаунта? <Link to={`/register?role=${role}`} className="font-medium text-accent hover:underline">Зарегистрироваться</Link></>}>
      <RoleSwitch role={role} base="/login" />
      {role === 'participant' && <>
        <FspSignInButton />
        {demo && <p className="mt-2 text-xs text-ink-3">демо: FSP001 / test</p>}
        <OrDivider />
      </>}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div>
          <label className="field-label" htmlFor="username">Email</label>
          <input id="username" {...register('username')} type="email" autoComplete="email" className="input"
            placeholder={role === 'participant' ? 'you@mail.ru' : 'hr@company.ru'} />
          {errors.username && <p className="field-error">{errors.username.message}</p>}
        </div>
        <div>
          <div className="flex items-baseline justify-between">
            <label className="field-label" htmlFor="password">Пароль</label>
            <Link to={`/forgot?role=${role}`} className="text-xs text-ink-3 hover:text-accent">Забыли пароль?</Link>
          </div>
          <input id="password" type="password" {...register('password')} autoComplete="current-password" className="input" />
          {errors.password && <p className="field-error">{errors.password.message}</p>}
        </div>
        {error && <p className="notice-error" role="alert">{error}</p>}
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full py-3">
          {isSubmitting ? 'Входим…' : 'Войти'}
        </button>
      </form>
      {offline && (
        <div className="mt-6 space-y-2 border-t border-line pt-4" data-testid="example-entry">
          <p className="text-xs leading-relaxed text-ink-3">Сервер не ответил. Пример кабинета открывается без входа: карточки учебные.</p>
          <button type="button" className="btn w-full border border-line py-2 text-sm"
            onClick={() => { enterExample('employer'); navigate('/employer/search') }}>Пример кабинета работодателя</button>
          <button type="button" className="btn w-full border border-line py-2 text-sm"
            onClick={() => { enterExample('participant'); navigate('/candidate') }}>Пример кабинета кандидата</button>
        </div>
      )}
      <div className="mt-6 flex flex-col gap-2 border-t border-line pt-4">
        {demo && (
          <Link to={`/register?role=${role}`} className="text-xs font-medium text-accent hover:underline">
            Без почты: гостевой аккаунт на 48 часов
          </Link>
        )}
        <p className="text-xs text-ink-3">Демо-аккаунты, пароль demo12345:</p>
        <p className="text-xs leading-relaxed text-ink-3">Демо-доступ для жюри: данные синтетические; свой прогресс можно сбросить кнопкой</p>
        {DEMO[role].map(([email, note]) => (
          <button key={email} type="button" className="chip-default w-full justify-start hover:border-accent hover:text-accent"
            onClick={() => { setValue('username', email); setValue('password', 'demo12345') }}>
            {email} <span className="text-ink-3">{note}</span>
          </button>
        ))}
        {demo && role === 'participant' && <>
          <p className="text-xs leading-relaxed text-ink-3">
            Для жюри: jury1@demo.talent … jury10@demo.talent, пароль demo12345 — у каждого свои попытки
          </p>
          <button type="button" className="btn w-full border border-line py-2 text-sm" onClick={takeJury}>
            Взять свободный аккаунт жюри
          </button>
        </>}
      </div>
    </AuthShell>
  )
}
