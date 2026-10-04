import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../store/authStore'
import { apiError, loginParticipant, loginEmployer } from '../api/client'

const schema = z.object({
  username: z.string().min(1, 'Обязательное поле'),
  password: z.string().min(1, 'Обязательное поле'),
})
type Form = z.infer<typeof schema>

export default function LoginPage() {
  const [params] = useSearchParams()
  const role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [error, setError] = useState('')

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({
    resolver: zodResolver(schema)
  })

  const onSubmit = async ({ username, password }: Form) => {
    setError('')
    try {
      const res = role === 'participant'
        ? await loginParticipant(username, password)
        : await loginEmployer(username, password)
      setAuth(res.data.access_token, res.data.refresh_token, role)
      navigate(role === 'participant' ? '/candidate' : '/employer')
    } catch (e: any) {
      setError(apiError(e, 'Ошибка входа'))
    }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center bg-surface-0">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold text-text-primary mb-2">Вход</h1>
        <p className="text-text-muted text-sm mb-6">
          {role === 'participant' ? 'Участник ФСП' : 'Работодатель'}
          {' · '}
          <Link to={`/login?role=${role === 'participant' ? 'employer' : 'participant'}`}
            className="text-fsp-violet hover:underline">
            переключить роль
          </Link>
        </p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              {role === 'participant' ? 'ID ФСП (напр. FSP001)' : 'Email'}
            </label>
            <input {...register('username')} className="input" />
            {errors.username && <p className="text-fsp-red text-xs mt-1">{errors.username.message}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">Пароль / секрет</label>
            <input type="password" {...register('password')} className="input" />
            {errors.password && <p className="text-fsp-red text-xs mt-1">{errors.password.message}</p>}
          </div>
          {error && <p className="text-fsp-red text-sm bg-red-50 rounded-lg px-4 py-2">{error}</p>}
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
            {isSubmitting ? 'Вход...' : 'Войти'}
          </button>
        </form>
        <p className="text-center text-sm text-text-muted mt-4">
          Нет аккаунта? <Link to="/register" className="text-brand-bright hover:underline">Зарегистрироваться</Link>
        </p>
        <p className="text-center text-xs text-text-muted mt-2">
          {role === 'participant' ? 'Демо: FSP001 / test · FSP002 / test' : 'Демо: hr@yandex.demo / demo12345'}
        </p>
      </div>
    </div>
  )
}
