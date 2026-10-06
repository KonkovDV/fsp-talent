import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { apiError, apiErrorCode, legalDocuments, registerEmployer, registerParticipant, type Role } from '../api/client'
import { ConsentChecklist, requiredKinds } from '../components/LegalConsents'
import AuthShell, { RoleSwitch } from '../components/AuthShell'
import FspSignInButton, { OrDivider } from '../components/FspSignInButton'

const participantSchema = z.object({
  display_name: z.string().min(2, 'Как к вам обращаться'),
  email: z.string().email('Проверьте email'),
  password: z.string().min(8, 'Минимум 8 символов'),
  is_adult: z.boolean(),
})
const employerSchema = z.object({
  company_name: z.string().min(2, 'Название компании'),
  email: z.string().email('Проверьте email'),
  password: z.string().min(8, 'Минимум 8 символов'),
  inn: z.string().regex(/^(\d{10}|\d{12})?$/, '10 или 12 цифр').optional(),
  website: z.string().optional(),
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

  const pf = useForm<ParticipantForm>({ resolver: zodResolver(participantSchema), defaultValues: { is_adult: false } })
  const ef = useForm<EmployerForm>({ resolver: zodResolver(employerSchema) })

  const done = (email: string) => navigate(`/verify?email=${encodeURIComponent(email)}&role=${role}`)
  const fail = (e: unknown) => {
    if (apiErrorCode(e) === 'email_taken') setError('Аккаунт с таким email уже есть. Войдите или сбросьте пароль.')
    else setError(apiError(e, 'Не удалось зарегистрироваться'))
  }
  const onParticipant = async (data: ParticipantForm) => {
    setError('')
    try { await registerParticipant({ ...data, consents }); done(data.email) } catch (e) { fail(e) }
  }
  const onEmployer = async (data: EmployerForm) => {
    setError('')
    try {
      await registerEmployer({ ...data, inn: data.inn || null, website: data.website || null, consents })
      done(data.email)
    } catch (e) { fail(e) }
  }
  const submitting = pf.formState.isSubmitting || ef.formState.isSubmitting
  const err = (m?: string) => m && <p className="field-error">{m}</p>

  return (
    <AuthShell title="Регистрация"
      lead={role === 'participant'
        ? 'Пройдёте опрос и тест — получите категорию, которую видят работодатели.'
        : 'Опишете, кого ищете, — подборка с объяснением появится сразу.'}
      aside={<>Есть аккаунт? <Link to={`/login?role=${role}`} className="font-medium text-accent hover:underline">Войти</Link></>}>
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
            <p className="field-hint">Не короче 8 символов.</p>
            {err(pf.formState.errors.password?.message)}</div>
          <label className="flex items-start gap-2.5 text-sm text-ink">
            <input type="checkbox" className="mt-1 accent-[rgb(var(--accent))]" {...pf.register('is_adult')} />
            <span>Мне исполнилось 18 лет<span className="block text-xs text-ink-3">Если нет, карточка скрыта от работодателей до согласия родителя.</span></span>
          </label>
          <p className="panel-quiet text-xs text-ink-2">
            История соревнований ФСП не нужна. ФСП ID можно привязать позже в профиле — результаты появятся
            в карточке отдельным подтверждённым блоком.
          </p>
          <ConsentChecklist role={role} value={consents} onChange={setConsents} />
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
            <p className="field-hint">Не короче 8 символов.</p>
            {err(ef.formState.errors.password?.message)}</div>
          <div><label className="field-label" htmlFor="inn">ИНН, если есть</label>
            <input id="inn" {...ef.register('inn')} inputMode="numeric" className="input" />
            {err(ef.formState.errors.inn?.message)}</div>
          <ConsentChecklist role={role} value={consents} onChange={setConsents} />
          {error && <p className="notice-error" role="alert">{error}</p>}
          <button type="submit" disabled={submitting || missing.length > 0} className="btn-primary w-full py-3">
            {submitting ? 'Отправляем код…' : 'Получить код на email'}
          </button>
        </form>
      )}
    </AuthShell>
  )
}
