import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../store/authStore'
import { apiError, registerParticipant, registerEmployer } from '../api/client'

const participantSchema = z.object({
  fsp_id: z.string().min(3, 'Введите ID ФСП (напр. FSP001)'),
  fsp_secret: z.string().min(1, 'Введите секрет (пароль из кабинета ФСП)'),
})
const employerSchema = z.object({
  company_name: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8, 'Минимум 8 символов'),
  inn: z.string().optional(),
  website: z.string().optional(),
})

export default function RegisterPage() {
  const [params] = useSearchParams()
  const role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [error, setError] = useState('')

  const { register: rp, handleSubmit: hp, formState: { errors: ep, isSubmitting: ip } } =
    useForm({ resolver: zodResolver(participantSchema) })
  const { register: re, handleSubmit: he, formState: { errors: ee, isSubmitting: ie } } =
    useForm({ resolver: zodResolver(employerSchema) })

  const onParticipant = async (data: any) => {
    setError('')
    try {
      const res = await registerParticipant(data)
      setAuth(res.data.access_token, res.data.refresh_token, 'participant')
      navigate('/candidate')
    } catch (e: unknown) { setError(apiError(e)) }
  }
  const onEmployer = async (data: any) => {
    setError('')
    try {
      const res = await registerEmployer(data)
      setAuth(res.data.access_token, res.data.refresh_token, 'employer')
      navigate('/employer')
    } catch (e: unknown) { setError(apiError(e)) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-fsp-light-bg">
      <div className="card w-full max-w-md">
        <h1 className="text-2xl font-bold mb-2">Регистрация</h1>
        <p className="text-gray-500 text-sm mb-6">
          {role === 'participant' ? 'Участник ФСП' : 'Работодатель'} ·{' '}
          <Link to={`/register?role=${role === 'participant' ? 'employer' : 'participant'}`}
            className="text-fsp-violet hover:underline">переключить</Link>
        </p>
        {role === 'participant' ? (
          <form onSubmit={hp(onParticipant)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ID ФСП</label>
              <input {...rp('fsp_id')} placeholder="FSP001"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
              {ep.fsp_id && <p className="text-fsp-red text-xs mt-1">{ep.fsp_id.message as string}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Секрет ФСП</label>
              <input type="password" {...rp('fsp_secret')} placeholder="из личного кабинета ФСП"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
              {ep.fsp_secret && <p className="text-fsp-red text-xs mt-1">{ep.fsp_secret.message as string}</p>}
            </div>
            {error && <p className="text-fsp-red text-sm bg-red-50 rounded-lg px-4 py-2">{error}</p>}
            <button type="submit" disabled={ip} className="btn-primary w-full">
              {ip ? 'Создание...' : 'Создать аккаунт'}
            </button>
            <p className="text-xs text-gray-400 text-center">Demo: FSP001 / test</p>
          </form>
        ) : (
          <form onSubmit={he(onEmployer)} className="space-y-4">
            {[['company_name','Название компании'], ['email','Email'], ['inn','ИНН (необязательно)']]
              .map(([field, label]) => (
              <div key={field}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input {...re(field as any)}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
              </div>
            ))}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Пароль</label>
              <input type="password" {...re('password')}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
              {ee.password && <p className="text-fsp-red text-xs mt-1">{ee.password.message as string}</p>}
            </div>
            {error && <p className="text-fsp-red text-sm bg-red-50 rounded-lg px-4 py-2">{error}</p>}
            <button type="submit" disabled={ie} className="btn-primary w-full">
              {ie ? 'Создание...' : 'Создать аккаунт'}
            </button>
          </form>
        )}
        <p className="text-center text-sm text-gray-500 mt-4">
          Есть аккаунт? <Link to="/login" className="text-fsp-violet hover:underline">Войти</Link>
        </p>
      </div>
    </div>
  )
}
