import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, apiErrorCode, downloadMyProfilePdf, getMyProfile, giveConsent, parseResume, updateMyProfile, updateVisibility, uploadResumePdf } from '../../api/client'
import { Eye, EyeOff, MailCheck } from 'lucide-react'
import { PageHeader, Skeleton } from '../../components/ui'
import { LegalDocModal } from '../../components/LegalConsents'
import FspLinkCard from '../../components/FspLinkCard'
import ConsentsPanel from '../../components/ConsentsPanel'
import AccountSecurity from '../../components/AccountSecurity'
import DeleteAccountCard from '../../components/DeleteAccountCard'
import SurveyCard, { type SurveyHint } from '../../components/SurveyCard'
import SkillPassport from '../../components/SkillPassport'
import ResumesCard from '../../components/ResumesCard'
import PassportCard from '../../components/PassportCard'
import { JOB_SEARCH_RU, roleRu } from '../../labels'

interface SkillRow { name: string; source_quote?: string | null; trust_level?: string; created_at?: string | null; confirmed_at?: string | null }
interface Quoted { value: string; quote: string }
interface ResumeFound {
  skills: SkillRow[]; llm_used?: boolean; note?: string; resume_token?: string | null
  full_name: Quoted | null; email: Quoted | null; phone: Quoted | null; telegram: Quoted | null
  experience_years: { value: number; quote: string } | null
  grade: Quoted | null; role: Quoted | null
  soft_skills: { name: string; quote: string }[]
}

export default function CandidateProfile() {
  const qc = useQueryClient()
  const { data: profile, isLoading } = useQuery({
    queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data),
  })
  const [newSkill, setNewSkill] = useState('')
  const [skills, setSkills] = useState<SkillRow[]>([])
  const [telegram, setTelegram] = useState('')
  const [phone, setPhone] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [publicProfile, setPublicProfile] = useState(false)
  const [resume, setResume] = useState('')
  const [resumeTokens, setResumeTokens] = useState<string[]>([])
  const [found, setFound] = useState<ResumeFound | null>(null)
  const [hint, setHint] = useState<SurveyHint | null>(null)
  const [note, setNote] = useState('')
  const [askDistribution, setAskDistribution] = useState(false)

  useEffect(() => {
    if (!profile) return
    setSkills(profile.skills ?? [])
    setTelegram(profile.telegram ?? '')
    setPhone(profile.phone ?? '')
    setDisplayName(profile.display_name ?? '')
    setPublicProfile(profile.public_profile)
  }, [profile])

  const save = useMutation({
    mutationFn: () => updateMyProfile({
      skills,
      resume_tokens: resumeTokens,
      telegram: telegram || null,
      phone: phone || null,
      public_profile: publicProfile,
      ...(displayName.trim() ? { display_name: displayName.trim() } : {}),
      ...(profile?.profile_version != null ? { expected_version: profile.profile_version } : {}),
    }),
    onSuccess: () => { setNote('Сохранено'); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: (error: unknown) => {
      // 152-FZ art. 10.1: a public page needs its own consent; ask for it instead of failing.
      if (apiErrorCode(error) === 'consent_required') { setAskDistribution(true); setNote(''); return }
      setNote(apiError(error, 'Ошибка сохранения'))
    },
  })
  const consentToPublic = useMutation({
    mutationFn: () => giveConsent('pd_distribution'),
    onSuccess: () => { setAskDistribution(false); save.mutate(); qc.invalidateQueries({ queryKey: ['myConsents'] }) },
    onError: (error: unknown) => setNote(apiError(error)),
  })
  const [readDoc, setReadDoc] = useState(false)
  const visibility = useMutation({
    mutationFn: (value: boolean) => updateVisibility(value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myProfile'] }),
  })
  const cardFields = useMutation({
    mutationFn: (patch: Record<string, boolean>) => updateMyProfile({
      ...patch,
      ...(profile?.profile_version != null ? { expected_version: profile.profile_version } : {}),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myProfile'] }),
    onError: (error: unknown) => setNote(apiError(error, 'Не удалось сохранить видимость карточки')),
  })
  const jobSearch = useMutation({
    mutationFn: (value: 'active' | 'open' | 'not_looking') => updateMyProfile({
      job_search: value,
      ...(profile?.profile_version != null ? { expected_version: profile.profile_version } : {}),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myProfile'] }),
    onError: (error: unknown) => setNote(apiError(error, 'Не удалось сохранить статус')),
  })
  const takeParsed = (result: ResumeFound) => {
    setSkills(prev => {
      const known = new Set(prev.map(item => item.name))
      return [...prev, ...result.skills.filter(item => !known.has(item.name))]
    })
    if (result.resume_token) {
      setResumeTokens(prev => prev.includes(result.resume_token!) ? prev : [...prev, result.resume_token!])
    }
    setFound(result)
    const skillsNote = result.skills.length
      ? (result.llm_used ? 'Навыки предложены моделью и правилами.' : 'Навыки добавлены в список.')
      : 'Навыков из словаря в тексте нет.'
    setNote(`${skillsNote} Поля ниже переносятся только по кнопке «Применить».`)
  }
  const parsed = useMutation({
    mutationFn: () => parseResume(resume).then(r => r.data as ResumeFound),
    onSuccess: takeParsed,
  })
  const applySurvey = (patch: Omit<SurveyHint, 'nonce'>, message: string) => {
    setHint(prev => ({ ...(prev ?? { nonce: 0 }), ...patch, nonce: Date.now() }))
    setNote(profile?.industry ? message : `${message} Сферу выберите в опросе.`)
  }

  if (isLoading || !profile) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-96" /></div>
  const addSkill = () => {
    const name = newSkill.trim()
    if (name && !skills.some(s => s.name.toLowerCase() === name.toLowerCase())) setSkills([...skills, { name }])
    setNewSkill('')
  }
  return (
    <div>
      <PageHeader title={profile.display_name ?? 'Профиль'}
        lead={profile.email
          ? <span className="inline-flex items-center gap-1.5"><MailCheck size={14} className="text-ok" aria-hidden />
            {profile.email} — подтверждён. Его получит работодатель, когда вы примете приглашение.</span>
          : <span>Вы входите через ФСП ID, email не указан. Добавьте Telegram или телефон: их получит работодатель, когда вы примете приглашение.</span>}
        actions={
          <button onClick={() => visibility.mutate(!profile.is_visible)} aria-pressed={profile.is_visible}
            className={profile.discoverable ? 'btn-secondary border-ok/50 text-ok' : 'btn-secondary'}>
            {profile.is_visible ? <Eye size={16} aria-hidden /> : <EyeOff size={16} aria-hidden />}
            {profile.discoverable ? 'Виден работодателям' : 'Скрыт из поиска'}
          </button>} />

      <section className="card mb-6" aria-labelledby="job-search-h">
        <h2 id="job-search-h" className="section-title">Поиск работы</h2>
        <p className="mt-1 text-sm text-ink-2">«Не ищу» убирает карточку из поиска и подборки. Согласие на публикацию при этом не отзывается.</p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          {(Object.keys(JOB_SEARCH_RU) as ('active' | 'open' | 'not_looking')[]).map(value => (
            <button key={value} type="button" aria-pressed={(profile.job_search ?? 'open') === value}
              disabled={jobSearch.isPending}
              onClick={() => jobSearch.mutate(value)}
              className={`w-full sm:flex-1 ${(profile.job_search ?? 'open') === value ? 'btn-primary' : 'btn-secondary'}`}>
              {JOB_SEARCH_RU[value]}
            </button>
          ))}
        </div>
      </section>

      <section className="card mb-6" aria-labelledby="city-h">
        <h2 id="city-h" className="section-title">Что видно на анонимной карточке</h2>
        <p className="mt-1 text-sm text-ink-2">Выключенное поле не печатается. Скрытый город не входит в балл: иначе его можно было бы вычислить фильтром. Навыки, которые совпали с запросом, остаются.</p>
        <div className="mt-4 flex flex-col gap-2">
          {([
            ['show_city', 'Город виден работодателям', 'Город скрыт'],
            ['show_stack', 'Стек виден', 'Стек скрыт'],
            ['show_experience', 'Опыт виден', 'Опыт скрыт'],
            ['show_fsp', 'Результаты ФСП видны', 'Результаты ФСП скрыты'],
          ] as const).map(([field, on, off]) => {
            const shown = profile[field] !== false
            return (
              <button key={field} type="button" aria-pressed={shown} disabled={cardFields.isPending}
                onClick={() => cardFields.mutate({ [field]: !shown })}
                className={shown ? 'btn-primary' : 'btn-secondary'}>
                {shown ? on : off}
              </button>
            )
          })}
        </div>
      </section>

      <section className="card mb-6" aria-labelledby="soft-h">
        <h2 id="soft-h" className="section-title">Мягкие навыки</h2>
        <p className="mt-1 text-sm text-ink-2">Печатаются на карточке. В балл подбора не входят.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {['Коммуникация', 'Командная работа', 'Наставничество', 'Лидерство', 'Публичные выступления'].map(name => {
            const on = (profile.soft_skills ?? []).includes(name)
            return (
              <button key={name} type="button" aria-pressed={on} className={on ? 'chip-active' : 'chip-default'}
                onClick={() => {
                  const next = on ? (profile.soft_skills ?? []).filter((item: string) => item !== name) : [...(profile.soft_skills ?? []), name]
                  updateMyProfile({ soft_skills: next, ...(profile.profile_version != null ? { expected_version: profile.profile_version } : {}) })
                    .then(() => qc.invalidateQueries({ queryKey: ['myProfile'] }))
                    .catch((error: unknown) => setNote(apiError(error)))
                }}>{name}</button>
            )
          })}
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-6">
          <section className="card space-y-5" aria-labelledby="skills-h">
            <div>
              <h2 id="skills-h" className="section-title">Паспорт навыков</h2>
              <p className="mt-1 text-sm text-ink-2">Навык, подтверждённый тестом, весит в подборке больше цитаты из резюме, а цитата — больше простого заявления.</p>
            </div>
            <SkillPassport skills={skills} onRemove={name => setSkills(skills.filter(item => item.name !== name))} />
            <form className="flex gap-2" onSubmit={e => { e.preventDefault(); addSkill() }}>
              <input value={newSkill} onChange={e => setNewSkill(e.target.value)} placeholder="Например, PostgreSQL" className="input" aria-label="Новый навык" />
              <button className="btn-secondary shrink-0" disabled={!newSkill.trim()}>Добавить</button>
            </form>
            <div>
              <label className="field-label" htmlFor="resume">Текст резюме</label>
              <textarea id="resume" value={resume} onChange={e => setResume(e.target.value)} rows={4}
                placeholder="Вставьте резюме: навык попадёт в список, только если он прямо упомянут в тексте"
                className="input" />
              <div className="mt-2 flex flex-wrap gap-x-4">
              <label className="btn-ghost cursor-pointer px-0 text-accent">
                Загрузить PDF
                <input type="file" accept="application/pdf,.pdf" className="sr-only" onChange={e => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (!file) return
                  if (file.size > 5_000_000) {
                    setNote('PDF до 5 МБ, до 30 страниц')
                    return
                  }
                  uploadResumePdf(file).then(r => {
                    setResume(r.data.text ?? '')
                    takeParsed(r.data as ResumeFound)
                  }).catch((err: unknown) => setNote(apiError(err, 'PDF не разобран')))
                }} />
              </label>
              <button type="button" className="btn-ghost px-0 text-accent" onClick={() => {
                downloadMyProfilePdf().then(r => {
                  const url = URL.createObjectURL(r.data)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'profile.pdf'
                  a.click()
                  URL.revokeObjectURL(url)
                }).catch(() => setNote('PDF профиля не собрался'))
              }}>Скачать PDF профиля</button>
              <button onClick={() => parsed.mutate()} disabled={!resume || parsed.isPending} className="btn-ghost px-0 text-accent">
                {parsed.isPending ? 'Разбираем…' : 'Разобрать резюме'}
              </button>
              </div>
              <p className="mt-2 text-sm text-ink-2">PDF до 5 МБ, до 30 страниц.</p>
              {found && <ResumeFields found={found} onName={value => { setDisplayName(value); setNote('Имя подставлено в контакты. Сохраните изменения.') }}
                onPhone={value => { setPhone(value); setNote('Телефон подставлен. Сохраните изменения.') }}
                onTelegram={value => { setTelegram(value); setNote('Telegram подставлен. Сохраните изменения.') }}
                onSurvey={applySurvey} />}
            </div>
          </section>

          <section className="card space-y-4" aria-labelledby="contacts-h">
            <h2 id="contacts-h" className="section-title">Контакты для работодателя</h2>
            <p className="text-sm text-ink-2">Видны только компании, чьё приглашение вы приняли.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2"><label className="field-label" htmlFor="name">Имя в профиле</label>
                <input id="name" value={displayName} onChange={e => setDisplayName(e.target.value)} className="input" autoComplete="name" /></div>
              <div><label className="field-label" htmlFor="tg">Telegram</label>
                <input id="tg" value={telegram} onChange={e => setTelegram(e.target.value)} placeholder="@username" className="input" /></div>
              <div><label className="field-label" htmlFor="phone">Телефон</label>
                <input id="phone" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+7" className="input" /></div>
            </div>
            <label className="flex items-start gap-2.5 text-sm text-ink">
              <input type="checkbox" className="mt-1" checked={publicProfile} disabled={profile.is_minor}
                onChange={e => setPublicProfile(e.target.checked)} />
              <span>Публичная страница и место в рейтинге
                <span className="block text-xs text-ink-3">{profile.is_minor ? 'Недоступно до 18 лет.' : 'Имя, регион, категория и результаты ФСП; контакты не публикуются.'}</span></span>
            </label>
            {askDistribution && (
              <div className="notice-info flex-col" role="alert">
                <p>Для публичной страницы нужно отдельное согласие на распространение данных (ст. 10.1 152-ФЗ).</p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => consentToPublic.mutate()} className="btn-primary btn-sm">Даю согласие</button>
                  <button onClick={() => setReadDoc(true)} className="btn-secondary btn-sm">Прочитать текст</button>
                  <button onClick={() => { setAskDistribution(false); setPublicProfile(false) }} className="btn-ghost btn-sm">Отмена</button>
                </div>
              </div>
            )}
            {readDoc && <LegalDocModal kind="pd_distribution" onClose={() => setReadDoc(false)} />}
          </section>

          <div className="flex flex-wrap items-center gap-3">
            <button onClick={() => save.mutate()} disabled={save.isPending} className="btn-primary">{save.isPending ? 'Сохраняем…' : 'Сохранить изменения'}</button>
            {note && <p className="text-sm text-ink-2" role="status">{note}</p>}
          </div>
        </div>

        <aside className="space-y-6">
          <SurveyCard profile={profile} compact hint={hint} />
          <ResumesCard />
          <PassportCard />
          <FspLinkCard profile={profile} />
          <ConsentsPanel />
          <AccountSecurity />
          <DeleteAccountCard />
        </aside>
      </div>
    </div>
  )
}

function ResumeFields({ found, onName, onPhone, onTelegram, onSurvey }: {
  found: ResumeFound
  onName: (value: string) => void
  onPhone: (value: string) => void
  onTelegram: (value: string) => void
  onSurvey: (patch: Omit<SurveyHint, 'nonce'>, message: string) => void
}) {
  const row = (label: string, value: string, quote: string, onApply?: () => void) => (
    <div key={label} className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
      <p className="min-w-0 text-sm text-ink"><span className="text-ink-2">{label}.</span> {value}
        <span className="mt-0.5 block text-xs text-ink-3">«{quote}»</span></p>
      {onApply && <button type="button" onClick={onApply} className="btn-ghost shrink-0 px-0 text-accent">Применить</button>}
    </div>
  )
  const empty = !found.full_name && !found.email && !found.phone && !found.telegram
    && !found.experience_years && !found.grade && !found.role && found.soft_skills.length === 0
  return (
    <div className="space-y-3 rounded-xl border border-line bg-sunken/40 p-3">
      <p className="field-label">Нашлось в резюме</p>
      {empty && <p className="text-sm text-ink-2">Имени, контактов, стажа, грейда и роли в тексте нет. Навыки из словаря уже добавлены в список.</p>}
      {found.full_name && row('Имя', found.full_name.value, found.full_name.quote, () => onName(found.full_name!.value))}
      {found.phone && row('Телефон', found.phone.value, found.phone.quote, () => onPhone(found.phone!.value))}
      {found.telegram && row('Telegram', found.telegram.value, found.telegram.quote, () => onTelegram(found.telegram!.value))}
      {found.email && row('Почта в резюме', found.email.value, found.email.quote)}
      {found.email && <p className="text-xs text-ink-3">Входная почта аккаунта из резюме не меняется.</p>}
      {found.role && row('Специализация', roleRu(found.role.value), found.role.quote,
        () => onSurvey({ specialization: found.role!.value }, 'Специализация подставлена в опрос. Сохраните опрос.'))}
      {found.grade && row('Заявленный грейд', found.grade.value, found.grade.quote,
        () => onSurvey({ declared_grade: found.grade!.value }, 'Заявленный грейд подставлен в опрос. Сохраните опрос. Грейд, подтверждённый тестом, резюме не меняет.'))}
      {found.experience_years && row('Опыт, лет', String(found.experience_years.value), found.experience_years.quote,
        () => onSurvey({ experience_years: found.experience_years!.value }, 'Стаж подставлен в опрос. Сохраните опрос.'))}
      {found.soft_skills.length > 0 && (
        <div className="text-sm text-ink">
          <p className="text-ink-2">Мягкие навыки, в поиск не входят</p>
          <ul className="mt-1 space-y-1">
            {found.soft_skills.map(item => <li key={item.name}>{item.name} <span className="text-xs text-ink-3">«{item.quote}»</span></li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
