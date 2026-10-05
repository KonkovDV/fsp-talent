import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../store/authStore'
import { apiError, apiErrorCode, loginParticipant, loginEmployer } from '../api/client'
import { ArrowRight, User, Briefcase, Medal, Shield } from 'lucide-react'

const schema = z.object({
  username: z.string().email('Введите email'),
  password: z.string().min(1, 'Обязательное поле'),
})
type Form = z.infer<typeof schema>

const BENEFITS = [
  { Icon: Medal,  text: 'Официальные данные ФСП' },
  { Icon: Shield, text: 'Контакты только после согласия' },
  { Icon: User,   text: 'Анонимный поиск для работодателей' },
]

export default function LoginPage() {
  const [params] = useSearchParams()
  const role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [error, setError] = useState('')

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async ({ username, password }: Form) => {
    setError('')
    try {
      const res = role === 'participant'
        ? await loginParticipant(username, password)
        : await loginEmployer(username, password)
      setAuth(res.data.access_token, res.data.refresh_token, role)
      navigate(role === 'participant' ? '/candidate' : '/employer')
    } catch (e: unknown) {
      if (apiErrorCode(e) === 'email_not_verified') {
        navigate(`/verify?email=${encodeURIComponent(username.trim().toLowerCase())}&role=${role}`)
        return
      }
      setError(apiError(e, 'Ошибка входа'))
    }
  }

  const isParticipant = role === 'participant'

  return (
    <div className="min-h-dvh flex">

      {/* ── LEFT: ФСП Brand Panel ─────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-[420px] xl:w-[480px] flex-col justify-between p-10 shrink-0"
        style={{ background: 'linear-gradient(150deg, #06133A 0%, #0A1F5C 40%, #1B3FA0 100%)' }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 select-none">
          <div
            style={{
              width: 44, height: 44,
              background: 'linear-gradient(135deg, #D42330, #FF4D5A)',
              clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <span style={{ color: '#fff', fontWeight: 900, fontSize: 18 }}>Ф</span>
          </div>
          <div className="flex flex-col" style={{ lineHeight: 1 }}>
            <span style={{ color: '#fff', fontWeight: 900, fontSize: 20, letterSpacing: '0.04em', fontFamily: 'Montserrat, Inter, sans-serif' }}>ФСП ТАЛАНТ</span>
            <span style={{ color: 'rgba(255,255,255,0.45)', fontWeight: 500, fontSize: 11, letterSpacing: '0.1em' }}>ФЕДЕРАЦИЯ СПОРТИВНОГО ПРОГРАММИРОВАНИЯ</span>
          </div>
        </div>

        {/* Main promo text */}
        <div className="space-y-6">
          <h2 style={{ color: '#fff', fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900, fontSize: 28, lineHeight: 1.2 }}>
            {isParticipant
              ? 'Покажи свои результаты ФСП работодателям'
              : 'Найди лучших ИТ-специалистов России'
            }
          </h2>
          <div className="space-y-3">
            {BENEFITS.map(({ Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: 'rgba(29,130,245,0.25)', border: '1px solid rgba(29,130,245,0.4)' }}
                >
                  <Icon size={15} style={{ color: '#1D82F5' }} />
                </div>
                <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: 14, fontWeight: 500 }}>{text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom caption */}
        <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>
          Официальная платформа · LCT-2026 · 152-ФЗ
        </p>
      </div>

      {/* ── RIGHT: Form Panel ────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center bg-surface-0 px-6 py-12">
        <div className="w-full max-w-md space-y-8">

          {/* Role switch */}
          <div className="flex rounded-lg overflow-hidden border border-border">
            {(['participant', 'employer'] as const).map(r => (
              <Link
                key={r}
                to={`/login?role=${r}`}
                className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-semibold transition-colors ${
                  role === r
                    ? 'text-white'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
                style={role === r ? { background: '#1B3FA0' } : {}}
              >
                {r === 'participant' ? <User size={14} /> : <Briefcase size={14} />}
                {r === 'participant' ? 'Кандидат' : 'Работодатель'}
              </Link>
            ))}
          </div>

          {/* Heading */}
          <div>
            <h1 className="text-2xl font-black text-text-primary" style={{ fontFamily: 'Montserrat, Inter, sans-serif' }}>
              Вход в систему
            </h1>
            <p className="text-text-muted text-sm mt-1">
              {isParticipant ? 'Кандидат: с историей ФСП или без неё' : 'Аккаунт работодателя'}
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-semibold text-text-secondary mb-1.5">
                Email
              </label>
              <input {...register('username')} type="email" autoComplete="email" className="input" placeholder={isParticipant ? 'you@mail.ru' : 'hr@company.ru'} />
              {errors.username && <p className="text-xs mt-1" style={{ color: '#D42330' }}>{errors.username.message}</p>}
            </div>

            <div>
              <label className="block text-sm font-semibold text-text-secondary mb-1.5">Пароль</label>
              <input type="password" {...register('password')} autoComplete="current-password" className="input" placeholder="••••••••" />
              <Link to={`/forgot?role=${role}`} className="text-xs text-text-muted hover:underline">Забыли пароль?</Link>
              {errors.password && <p className="text-xs mt-1" style={{ color: '#D42330' }}>{errors.password.message}</p>}
            </div>

            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm"
                style={{ background: 'rgba(212,35,48,0.1)', border: '1px solid rgba(212,35,48,0.3)', color: '#FF6B75' }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full btn font-bold py-3 rounded-md text-white gap-2"
              style={{ background: isSubmitting ? '#999' : '#1B3FA0' }}
            >
              {isSubmitting ? 'Вхожу...' : 'Войти'}
              <ArrowRight size={16} />
            </button>
          </form>

          <div className="text-center space-y-2">
            <p className="text-sm text-text-muted">
              Нет аккаунта?{' '}
              <Link to={`/register?role=${role}`} style={{ color: '#1D82F5', fontWeight: 600 }} className="hover:underline">
                Зарегистрироваться
              </Link>
            </p>
            <p className="text-xs text-text-muted">
              {isParticipant
                ? 'Демо (пароль demo12345): fsp001@demo.talent · fsp002@demo.talent · nofsp@demo.talent (без ФСП)'
                : 'Демо: hr@sibcode.demo / demo12345'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
