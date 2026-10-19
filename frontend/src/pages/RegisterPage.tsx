import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { apiError, apiErrorCode, guestLogin, legalDocuments, publicDemo, registerEmployer, registerParticipant, type Role } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { ConsentChecklist, requiredKinds } from '../components/LegalConsents'
import DemoStandNotice from '../components/DemoStandNotice'
import AuthShell, { RoleSwitch } from '../components/AuthShell'
import FspSignInButton, { OrDivider } from '../components/FspSignInButton'
import { passwordRule } from '../passwordRule'

const participantSchema = z.object({
  display_name: z.string().min(2, 'Как к вам обращаться'),
  email: z.string().email('Проверьте email'),
  password: passwordRule,
  is_adult: z.boolean(),
  age_15_17: z.boolean(),
  birth_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Укажите дату рождения'),
  synthetic_ack: z.boolean().optional(),
}).refine(v => v.is_adult || v.age_15_17, { message: 'Регистрация открыта с 15 лет', path: ['age_15_17'] })
const employerSchema = z.object({
  company_name: z.string().min(2, 'Название компании'),
  email: z.string().email('Проверьте email'),
  password: passwordRule,
  inn: z.string().regex(/^(\d{10}|\d{12})?$/, '10 или 12 цифр').optional(),
  website: z.string().optional(),
  synthetic_ack: z.boolean().optional(),
})
type ParticipantForm = z.infer<typeof participantSchema>
type EmployerForm = z.infer<typeof employerSchema>

export default function RegisterPage() {
  const [params] = useSearchParams()
  const role: Role = params.get('role') === 'employer' ? 'employer' : 'participant'
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [consents, setConsents] = useState<string[]>([])
  const { data: docs } = useQuery({
    queryKey: ['legal-list', role], queryFn: () => legalDocuments(role).then(r => r.data),
  })
  const missing = requiredKinds(docs).filter(k => !consents.includes(k))
  const setAuth = useAuthStore(s => s.setAuth)
  const [demo, setDemo] = useState(false)
  const [guestBusy, setGuestBusy] = useState(false)
  useEffect(() => {
    publicDemo().then(res => setDemo(Boolean(res.data.demo_mode))).catch(() => setDemo(false))
  }, [])

  const pf = useForm<ParticipantForm>({ resolver: zodResolver(participantSchema), defaultValues: { is_adult: false, age_15_17: false } })
  const ef = useForm<EmployerForm>({ resolver: zodResolver(employerSchema) })

  // demo_code comes only from a demo stand without mail; it travels in history state, not in the address.
  const done = (email: string, demoCode?: string | null) =>
    navigate(`/verify?email=${encodeURIComponent(email)}&role=${role}`, { state: { demoCode: demoCode ?? null } })
  const fail = (e: unknown) => {
    if (apiErrorCode(e) === 'email_taken') setError('Аккаунт с таким email уже есть. Войдите или сбросьте пароль.')
    else setError(apiError(e, 'Не удалось зарегистрироваться'))
  }
  const onParticipant = async (data: ParticipantForm) => {
    setError('')
    if (demo && !data.synthetic_ack) {
      setError('На демо-стенде отметьте, что имя, почта и дата рождения вымышлены.')
      return
    }
    try { const r = await registerParticipant({ ...data, synthetic_ack: Boolean(data.synthetic_ack), consents }); done(data.email, r.data?.demo_code) } catch (e) { fail(e) }
  }
  const onEmployer = async (data: EmployerForm) => {
    setError('')
    if (demo && !data.synthetic_ack) {
      setError('На демо-стенде отметьте, что данные компании вымышлены.')
      return
    }
    try {
      const r = await registerEmployer({ ...data, inn: data.inn || null, website: data.website || null, synthetic_ack: Boolean(data.synthetic_ack), consents })
      done(data.email, r.data?.demo_code)
    } catch (e) { fail(e) }
  }
  const onGuest = async () => {
    setError('')
    setGuestBusy(true)
    try {
      const r = await guestLogin(role, consents)
      setAuth(r.data.access_token, role, r.data.guest_until)
      navigate(role === 'participant' ? '/candidate' : '/employer')
    } catch (e) {
      setError(apiError(e, 'Не удалось войти гостем'))
    } finally {
      setGuestBusy(false)
    }
  }
  const submitting = pf.formState.isSubmitting || ef.formState.isSubmitting
  const err = (m?: string) => m && <p className="field-error">{m}</p>

  return (
    <AuthShell title="Регистрация"
      lead={role === 'participant'
        ? 'Пройдёте опрос и тест — получите категорию, которую видят работодатели.'
        : 'Опишете, кого ищете, — подборка с объяснением появится сразу.'}
      aside={<>Есть аккаунт? <Link to={`/login?role=${role}`} className="font-medium text-accent hover:underline">Войти</Link></>}>
      <DemoStandNotice className="mb-4" />
      <RoleSwitch role={role} base="/register" />
      {role === 'participant' && <><FspSignInButton label="Продолжить через ФСП ID" /><OrDivider /></>}
      {role === 'participant' ? (
        <form onSubmit={pf.handleSubmit(onParticipant)} className="space-y-4" noValidate>
          <div><label className="field-label" htmlFor="display_name">Имя</label>
            <input id="display_name" {...pf.register('display_name')} className="input" autoComplete="name" />
            {err(pf.formState.errors.display_name?.message)}</div>
          <div><label className="field-label" htmlFor="email">Email</label>
            <input id="email" {...pf.register('email')} type="email" className="input" autoComplete="email" />
            {err(pf.formState.errors.email?.message)}</div>
          <div><label className="field-label" htmlFor="password">Пароль</label>
            <input id="password" {...pf.register('password')} type="password" className="input" autoComplete="new-password" />
            <p className="field-hint">Не короче 8 символов, не длиннее 72 байт (кириллица: до 36 букв).</p>
            {err(pf.formState.errors.password?.message)}</div>
          <div><label className="field-label" htmlFor="birth_date">Дата рождения</label>
            <input id="birth_date" {...pf.register('birth_date')} type="date" className="input" autoComplete="bday" />
            <p className="field-hint">Без даты работодатели вас в поиске не увидят: возраст проверяется по дате, а не по отметке.</p>
            {err(pf.formState.errors.birth_date?.message)}</div>
          <label className="flex items-start gap-2.5 text-sm text-ink">
            <input type="checkbox" className="mt-1 accent-[rgb(var(--accent))]" {...pf.register('is_adult')} />
            <span>Мне исполнилось 18 лет<span className="block text-xs text-ink-3">Если нет, карточка скрыта от работодателей до согласия родителя.</span></span>
          </label>
          {!pf.watch('is_adult') && (
            <label className="flex items-start gap-2.5 text-sm text-ink">
              <input type="checkbox" className="mt-1 accent-[rgb(var(--accent))]" {...pf.register('age_15_17')} />
              <span>Мне 15, 16 или 17 лет<span className="block text-xs text-ink-3">После входа укажите email родителя или другого законного представителя: он подтвердит согласие по ссылке из письма. Младше 15 лет регистрация закрыта.</span></span>
            </label>
          )}
          {err(pf.formState.errors.age_15_17?.message)}
          <p className="panel-quiet text-xs text-ink-2">
            История соревнований ФСП не нужна. ФСП ID можно привязать позже в профиле — результаты появятся
            в карточке отдельным подтверждённым блоком.
          </p>
          {demo && (
            <label className="flex items-start gap-2.5 text-sm text-ink">
              <input type="checkbox" className="mt-1 accent-[rgb(var(--accent))]" {...pf.register('synthetic_ack')} />
              <span>Имя, почта и дата рождения вымышлены. Настоящие персональные данные на этот стенд не отправляю.</span>
            </label>
          )}
          <ConsentChecklist role={role} value={consents} onChange={setConsents} />
          <p className="text-xs text-ink-3">Как мы обращаемся с данными — в{' '}
            <Link to="/privacy" className="text-accent underline">политике обработки персональных данных</Link>.</p>
          {error && <p className="notice-error" role="alert">{error}</p>}
          <button type="submit" disabled={submitting || missing.length > 0} className="btn-primary w-full py-3">
            {submitting ? 'Отправляем код…' : 'Получить код на email'}
          </button>
        </form>
      ) : (
        <form onSubmit={ef.handleSubmit(onEmployer)} className="space-y-4" noValidate>
          <div><label className="field-label" htmlFor="company_name">Название компании</label>
            <input id="company_name" {...ef.register('company_name')} className="input" />
            {err(ef.formState.errors.company_name?.message)}</div>
          <div><label className="field-label" htmlFor="email">Рабочий email</label>
            <input id="email" {...ef.register('email')} type="email" className="input" autoComplete="email" />
            {err(ef.formState.errors.email?.message)}</div>
          <div><label className="field-label" htmlFor="password">Пароль</label>
            <input id="password" {...ef.register('password')} type="password" className="input" autoComplete="new-password" />
            <p className="field-hint">Не короче 8 символов, не длиннее 72 байт (кириллица: до 36 букв).</p>
            {err(ef.formState.errors.password?.message)}</div>
          <div><label className="field-label" htmlFor="inn">ИНН, если есть</label>
            <input id="inn" {...ef.register('inn')} inputMode="numeric" className="input" />
            {err(ef.formState.errors.inn?.message)}</div>
          {demo && (
            <label className="flex items-start gap-2.5 text-sm text-ink">
              <input type="checkbox" className="mt-1 accent-[rgb(var(--accent))]" {...ef.register('synthetic_ack')} />
              <span>Название, почта и ИНН вымышлены. Настоящие данные компании на этот стенд не отправляю.</span>
            </label>
          )}
          <ConsentChecklist role={role} value={consents} onChange={setConsents} />
          <p className="text-xs text-ink-3">Как мы обращаемся с данными — в{' '}
            <Link to="/privacy" className="text-accent underline">политике обработки персональных данных</Link>.</p>
          {error && <p className="notice-error" role="alert">{error}</p>}
          <button type="submit" disabled={submitting || missing.length > 0} className="btn-primary w-full py-3">
            {submitting ? 'Отправляем код…' : 'Получить код на email'}
          </button>
        </form>
      )}
      {demo && (
        <div className="mt-6 space-y-2 border-t border-line pt-4" data-testid="guest-entry">
          <p className="text-xs leading-relaxed text-ink-3">
            Демо-стенд: можно войти без почты. Пустой гостевой аккаунт живёт 48 часов, потом удаляется.
            {role === 'participant' ? ' Гостя не видно в поиске работодателей.' : ''} Нужны те же согласия, что и выше.
          </p>
          <button type="button" className="btn w-full border border-line py-2 text-sm" onClick={onGuest}
            disabled={guestBusy || missing.length > 0}>
            {guestBusy ? 'Входим…' : 'Войти гостем без почты'}
          </button>
        </div>
      )}
    </AuthShell>
  )
}
