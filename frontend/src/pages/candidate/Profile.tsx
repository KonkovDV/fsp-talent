import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, apiErrorCode, getMyProfile, giveConsent, parseResume, updateMyProfile, updateVisibility } from '../../api/client'
import { Eye, EyeOff, MailCheck } from 'lucide-react'
import { LegalDocModal } from '../../components/LegalConsents'
import FspLinkCard from '../../components/FspLinkCard'
import ConsentsPanel from '../../components/ConsentsPanel'

const GRADES = ['', 'junior', 'middle', 'senior', 'lead']

interface SkillRow { name: string; source_quote?: string | null }

export default function CandidateProfile() {
  const qc = useQueryClient()
  const { data: profile, isLoading } = useQuery({
    queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data),
  })
  const [experience, setExperience] = useState('')
  const [grade, setGrade] = useState('')
  const [skills, setSkills] = useState<SkillRow[]>([])
  const [telegram, setTelegram] = useState('')
  const [phone, setPhone] = useState('')
  const [publicProfile, setPublicProfile] = useState(false)
  const [resume, setResume] = useState('')
  const [note, setNote] = useState('')
  const [askDistribution, setAskDistribution] = useState(false)

  useEffect(() => {
    if (!profile) return
    setExperience(profile.experience_years == null ? '' : String(profile.experience_years))
    setGrade(profile.declared_grade ?? '')
    setSkills(profile.skills ?? [])
    setTelegram(profile.telegram ?? '')
    setPhone(profile.phone ?? '')
    setPublicProfile(profile.public_profile)
  }, [profile])

  const save = useMutation({
    mutationFn: () => updateMyProfile({
      experience_years: experience === '' ? null : Number(experience),
      declared_grade: grade || null,
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

  if (isLoading) return <div className="animate-pulse h-64 bg-gray-100 rounded-2xl" />
  if (!profile) return null
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{profile.display_name}</h1>
          <p className="text-sm text-text-muted">{profile.fsp_id ?? 'без ФСП ID'} · {profile.region ?? 'регион не указан'}</p>
          <p className="text-xs text-text-muted flex items-center gap-1 mt-1">
            <MailCheck size={12} className="text-green-600" />{profile.email} — подтверждён, его получит работодатель после вашего согласия
          </p>
        </div>
        <button onClick={() => visibility.mutate(!profile.is_visible)}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium ${profile.is_visible ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
          {profile.is_visible ? <Eye size={16} /> : <EyeOff size={16} />}
          {profile.discoverable ? 'Виден работодателям' : 'Скрыт из поиска'}
        </button>
      </div>

      <div className="card space-y-4">
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="text-sm">Опыт, лет
            <input type="number" min={0} max={50} value={experience} onChange={e => setExperience(e.target.value)}
              className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2" />
          </label>
          <label className="text-sm">Грейд (самооценка)
            <select value={grade} onChange={e => setGrade(e.target.value)} className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2">
              {GRADES.map(item => <option key={item} value={item}>{item || 'не указан'}</option>)}
            </select>
          </label>
          <label className="text-sm">Telegram
            <input value={telegram} onChange={e => setTelegram(e.target.value)} className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2" />
          </label>
          <label className="text-sm">Телефон
            <input value={phone} onChange={e => setPhone(e.target.value)} className="mt-1 w-full border border-gray-200 rounded-xl px-3 py-2" />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={publicProfile} disabled={profile.is_minor}
            onChange={e => setPublicProfile(e.target.checked)} />
          Именная публичная страница и лидерборд
          {profile.is_minor && <span className="text-gray-400">недоступно несовершеннолетним</span>}
        </label>
        {askDistribution && (
          <div className="rounded-xl border border-fsp-violet/30 bg-fsp-violet/5 p-4 text-sm space-y-2" role="alert">
            <p>Для публичной страницы нужно отдельное согласие на распространение данных (ст. 10.1 152-ФЗ).
              Публикуются имя, регион, категория и результаты ФСП; контакты и дата рождения не публикуются никогда.</p>
            <div className="flex gap-3">
              <button onClick={() => consentToPublic.mutate()} className="btn-primary text-sm">Даю согласие</button>
              <button onClick={() => setReadDoc(true)} className="btn-secondary text-sm">Прочитать текст</button>
              <button onClick={() => { setAskDistribution(false); setPublicProfile(false) }} className="text-sm text-text-muted">Отмена</button>
            </div>
          </div>
        )}
        {readDoc && <LegalDocModal kind="pd_distribution" onClose={() => setReadDoc(false)} />}
        <div>
          <p className="text-sm font-medium mb-2">Навыки</p>
          <div className="flex flex-wrap gap-2">
            {skills.map(skill => (
              <button key={skill.name} onClick={() => setSkills(skills.filter(item => item.name !== skill.name))}
                className="px-3 py-1 bg-fsp-violet/10 text-fsp-violet rounded-lg text-sm" title="Убрать">
                {skill.name} ×
              </button>
            ))}
          </div>
        </div>
        <textarea value={resume} onChange={e => setResume(e.target.value)} rows={4}
          placeholder="Вставьте резюме: навыки извлекутся только если есть в тексте"
          className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm" />
        <div className="flex gap-3">
          <button onClick={() => parsed.mutate()} disabled={!resume || parsed.isPending} className="btn-secondary text-sm">Разобрать резюме</button>
          <button onClick={() => save.mutate()} className="btn-primary text-sm">{save.isPending ? 'Сохраняем…' : 'Сохранить'}</button>
        </div>
        {note && <p className="text-sm text-text-secondary">{note}</p>}
        <div className="text-sm text-text-muted">
          <p>Роль: {profile.primary_role} · грейд: {profile.grade} ({profile.grade_source})</p>
          <ul className="mt-1">{(profile.explanation ?? []).map((line: string) => <li key={line}>{line}</li>)}</ul>
        </div>
        {(profile.discipline_scores ?? []).map((ds: { discipline: string; label: string; lcb: number; best_rank: string | null; confidence: number }) => (
          <p key={ds.discipline} className="text-sm font-mono">
            {ds.label}: LCB {ds.lcb.toFixed(2)} · уверенность {Math.round(ds.confidence * 100)}%
            {ds.best_rank ? ` · ${ds.best_rank}` : ''}
          </p>
        ))}
      </div>
      <FspLinkCard profile={profile} />
      <ConsentsPanel />
    </div>
  )
}
