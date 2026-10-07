import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../store/authStore'
import { apiError, apiErrorCode, loginEmployer, loginParticipant } from '../api/client'
import AuthShell, { RoleSwitch } from '../components/AuthShell'
import FspSignInButton, { OrDivider } from '../components/FspSignInButton'

const schema = z.object({
  username: z.string().email('Введите email'),
  password: z.string().min(1, 'Введите пароль'),
})
type Form = z.infer<typeof schema>

const DEMO = {
  participant: [['fsp001@demo.talent', 'с историей ФСП'], ['nofsp@demo.talent', 'без ФСП']],
  employer: [['hr@sibcode.demo', '«Сибирский код»']],
}

export default function LoginPage() {
  const [params] = useSearchParams()
  const role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [error, setError] = useState('')
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) })

  const onSubmit = async ({ username, password }: Form) => {
    setError('')
    try {
      const res = role === 'participant' ? await loginParticipant(username, password) : await loginEmployer(username, password)
      setAuth(res.data.access_token, role)
      navigate(role === 'participant' ? '/candidate' : '/employer')
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
      {role === 'participant' && <><FspSignInButton /><OrDivider /></>}
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
      <div className="mt-6 border-t border-line pt-4">
        <p className="text-xs text-ink-3">Демо-аккаунты, пароль demo12345:</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {DEMO[role].map(([email, note]) => (
            <button key={email} type="button" className="chip-default hover:border-accent hover:text-accent"
              onClick={() => { setValue('username', email); setValue('password', 'demo12345') }}>
              {email} <span className="text-ink-3">{note}</span>
            </button>
          ))}
        </div>
      </div>
    </AuthShell>
  )
}
