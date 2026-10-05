import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, apiErrorCode, downloadMyProfilePdf, getMyProfile, giveConsent, parseResume, updateMyProfile, updateVisibility, uploadResumePdf } from '../../api/client'
import { Eye, EyeOff, MailCheck, X } from 'lucide-react'
import { PageHeader, Skeleton } from '../../components/ui'
import { LegalDocModal } from '../../components/LegalConsents'
import FspLinkCard from '../../components/FspLinkCard'
import ConsentsPanel from '../../components/ConsentsPanel'
import DeleteAccountCard from '../../components/DeleteAccountCard'
import SurveyCard from '../../components/SurveyCard'

interface SkillRow { name: string; source_quote?: string | null; trust_level?: string }

export default function CandidateProfile() {
  const qc = useQueryClient()
  const { data: profile, isLoading } = useQuery({
    queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data),
  })
  const [newSkill, setNewSkill] = useState('')
  const [skills, setSkills] = useState<SkillRow[]>([])
  const [telegram, setTelegram] = useState('')
  const [phone, setPhone] = useState('')
  const [publicProfile, setPublicProfile] = useState(false)
  const [resume, setResume] = useState('')
  const [note, setNote] = useState('')
  const [askDistribution, setAskDistribution] = useState(false)

  useEffect(() => {
    if (!profile) return
    setSkills(profile.skills ?? [])
    setTelegram(profile.telegram ?? '')
    setPhone(profile.phone ?? '')
    setPublicProfile(profile.public_profile)
  }, [profile])

  const save = useMutation({
    mutationFn: () => updateMyProfile({
      skills,
      telegram: telegram || null,
      phone: phone || null,
      public_profile: publicProfile,
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
  const parsed = useMutation({
    mutationFn: () => parseResume(resume).then(r => r.data),
    onSuccess: (result) => {
      const known = new Set(skills.map(item => item.name))
      setSkills([...skills, ...result.skills.filter((item: SkillRow) => !known.has(item.name))])
      setNote(result.llm_used ? 'Навыки предложены моделью и правилами. Проверьте перед сохранением.' : result.note)
    },
  })

  if (isLoading || !profile) return <div className="space-y-4"><Skeleton className="h-10 w-72" /><Skeleton className="h-96" /></div>
  const addSkill = () => {
    const name = newSkill.trim()
    if (name && !skills.some(s => s.name.toLowerCase() === name.toLowerCase())) setSkills([...skills, { name }])
    setNewSkill('')
  }
  return (
    <div>
      <PageHeader title={profile.display_name ?? 'Профиль'}
        lead={<span className="inline-flex items-center gap-1.5"><MailCheck size={14} className="text-ok" aria-hidden />
          {profile.email} — подтверждён. Его получит работодатель, когда вы примете приглашение.</span>}
        actions={
          <button onClick={() => visibility.mutate(!profile.is_visible)} aria-pressed={profile.is_visible}
            className={profile.discoverable ? 'btn-secondary border-ok/50 text-ok' : 'btn-secondary'}>
            {profile.is_visible ? <Eye size={16} aria-hidden /> : <EyeOff size={16} aria-hidden />}
            {profile.discoverable ? 'Виден работодателям' : 'Скрыт из поиска'}
          </button>} />

      <div className="grid items-start gap-6 lg:grid-cols-[1.35fr_1fr]">
        <div className="space-y-6">
          <section className="card space-y-5" aria-labelledby="skills-h">
            <div>
              <h2 id="skills-h" className="section-title">Навыки</h2>
              <p className="mt-1 text-sm text-ink-2">Отмеченные галочкой подтверждены тестом и весят в поиске больше заявленных.</p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {skills.length === 0 && <p className="text-sm text-ink-3">Навыков пока нет: добавьте вручную или разберите резюме.</p>}
              {skills.map(skill => (
                <span key={skill.name} className={skill.trust_level === 'test_confirmed' ? 'chip-active' : 'chip-default'}>
                  {skill.name}{skill.trust_level === 'test_confirmed' && ' ✓'}
                  <button onClick={() => setSkills(skills.filter(item => item.name !== skill.name))} aria-label={`Убрать ${skill.name}`}
                    className="-mr-1 rounded-full p-0.5 hover:bg-sunken"><X size={12} /></button>
                </span>
              ))}
            </div>
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
                  uploadResumePdf(file).then(r => {
                    setResume(r.data.text ?? '')
                    const found = (r.data.skills ?? []) as { name: string }[]
                    if (found.length) setSkills(prev => {
                      const names = new Set(prev.map(s => s.name))
                      return [...prev, ...found.filter(s => !names.has(s.name))]
                    })
                    setNote(found.length ? `Из PDF: ${found.map(s => s.name).join(', ')}` : 'В PDF не нашлось навыков из словаря')
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
                {parsed.isPending ? 'Разбираем…' : 'Найти навыки в резюме'}
              </button>
              </div>
            </div>
          </section>

          <section className="card space-y-4" aria-labelledby="contacts-h">
            <h2 id="contacts-h" className="section-title">Контакты для работодателя</h2>
            <p className="text-sm text-ink-2">Видны только компании, чьё приглашение вы приняли.</p>
            <div className="grid gap-4 sm:grid-cols-2">
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
          <SurveyCard profile={profile} compact />
          <FspLinkCard profile={profile} />
          <ConsentsPanel />
          <DeleteAccountCard />
        </aside>
      </div>
    </div>
  )
}
