import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks } from 'lucide-react'
import { apiError, saveSurvey, surveyOptions } from '../api/client'
import { gradeRu } from '../labels'
import { grossForNet, netLine, netMonthly } from '../money'

export interface SurveyHint {
  specialization?: string
  declared_grade?: string
  experience_years?: number
  nonce: number
}

interface Props {
  profile: { specialization: string | null; industry: string | null; work_goal: string | null
    declared_grade: string | null; experience_years: number | null; survey_done: boolean
    salary_from?: number | null; salary_to?: number | null
    region?: string | null; work_formats?: string[] }
  compact?: boolean
  hint?: SurveyHint | null
}

/** Experience only suggests a grade; the candidate chooses it (Q&A), the test confirms it. */
function byExperience(years: number): string {
  return years < 2 ? 'junior' : years < 5 ? 'middle' : 'senior'
}

/** TZ 2.1: direction and specialization from the survey + declared grade + test make the category.
 * The TZ word «отрасль» is the IT direction; the subject area (fintech, retail…) is optional. */
export default function SurveyCard({ profile, compact, hint }: Props) {
  const qc = useQueryClient()
  const { data: opts } = useQuery({ queryKey: ['surveyOptions'], queryFn: () => surveyOptions().then(r => r.data) })
  const [spec, setSpec] = useState(profile.specialization ?? '')
  const [industry, setIndustry] = useState(profile.industry === 'any' ? '' : profile.industry ?? '')
  const [goal, setGoal] = useState(profile.work_goal ?? 'job')
  const [grade, setGrade] = useState(profile.declared_grade ?? '')
  const [years, setYears] = useState(profile.experience_years == null ? '' : String(profile.experience_years))
  const [payFrom, setPayFrom] = useState(profile.salary_from == null ? '' : String(profile.salary_from))
  const [payTo, setPayTo] = useState(profile.salary_to == null ? '' : String(profile.salary_to))
  const [basis, setBasis] = useState<'gross' | 'net'>('gross')
  const [city, setCity] = useState(profile.region ?? '')
  const [formats, setFormats] = useState<string[]>(profile.work_formats ?? [])
  const [note, setNote] = useState('')
  useEffect(() => {
    setSpec(profile.specialization ?? ''); setIndustry(profile.industry === 'any' ? '' : profile.industry ?? '')
    setGoal(profile.work_goal ?? 'job'); setGrade(profile.declared_grade ?? '')
  }, [profile.specialization, profile.industry, profile.work_goal, profile.declared_grade])
  useEffect(() => {
    if (!hint) return
    if (hint.specialization) setSpec(hint.specialization)
    if (hint.declared_grade) setGrade(hint.declared_grade)
    if (hint.experience_years != null) setYears(String(hint.experience_years))
  }, [hint])

  const save = useMutation({
    mutationFn: () => saveSurvey({ specialization: spec, industry: industry || 'any', work_goal: goal, declared_grade: grade,
      experience_years: years === '' ? null : Number(years),
      salary_from_gross: payFrom === '' ? null : Number(payFrom),
      salary_to_gross: payTo === '' ? null : Number(payTo),
      salary_basis: basis,
      work_formats: formats, region: city || null }),
    onSuccess: () => { setNote('Сохранено. Категория пересчитана.'); qc.invalidateQueries({ queryKey: ['myProfile'] }); qc.invalidateQueries({ queryKey: ['resumes'] }) },
    onError: (e: unknown) => setNote(apiError(e)),
  })
  const select = 'select mt-1'
  const entries = (o?: Record<string, string>) => Object.entries(o ?? {})

  return (
    <div className="card space-y-3" data-testid="survey">
      <div className="flex items-start gap-3">
        <ListChecks className="text-accent shrink-0 mt-0.5" size={20} />
        <div>
          <p className="section-title">{profile.survey_done ? 'Направление и специализация' : 'Шаг 1. Направление и специализация'}</p>
            {!compact && <p className="text-sm text-ink-2">Специализация задаёт категорию и состав теста.
            Грейд выбираете вы, подтверждает его только тест. Город и формат работы входят в балл, когда вакансия их называет, и из выдачи не убирают.</p>}
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <label>Специализация
          <select value={spec} onChange={e => setSpec(e.target.value)} className={select} aria-label="Специализация">
            <option value="">выберите</option>
            {entries(opts?.specializations).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Предметная область (необязательно)
          <select value={industry} onChange={e => setIndustry(e.target.value)} className={select} aria-label="Предметная область">
            <option value="">не важно</option>
            {entries(opts?.industries).filter(([k]) => k !== 'any').map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <span className="field-hint">Индустрия компании. Направление разработки задаёт специализация.</span>
        </label>
        <label>Что ищете
          <select value={goal} onChange={e => {
            const next = e.target.value
            setGoal(next)
            if (next === 'internship') setGrade('intern')
          }} className={select}>
            {entries(opts?.work_goals).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Ваш грейд
          <select value={grade} onChange={e => setGrade(e.target.value)} className={select} aria-label="Грейд" required>
            <option value="">выберите</option>
            {(opts?.grades ?? []).map((g: string) => <option key={g} value={g}>{gradeRu(g)}</option>)}
          </select>
          <span className="field-hint">
            {years !== '' && Number.isFinite(Number(years))
              ? `По стажу ${years} лет обычно выбирают ${gradeRu(byExperience(Number(years)))}. `
              : ''}
            Первый тест проверит именно этот грейд.
          </span>
        </label>
        <label>Опыт, лет
          <input type="number" min={0} max={50} value={years} onChange={e => setYears(e.target.value)} className="input mt-1" />
        </label>
        <label>Ожидания по зарплате, от
          <select value={basis} onChange={e => {
            const next = e.target.value as 'gross' | 'net'
            const conv = next === 'net' ? netMonthly : grossForNet
            setPayFrom(payFrom === '' ? '' : String(conv(Number(payFrom))))
            setPayTo(payTo === '' ? '' : String(conv(Number(payTo))))
            setBasis(next)
          }} className={select} aria-label="Зарплата до НДФЛ или на руки">
            <option value="gross">до вычета НДФЛ</option>
            <option value="net">на руки</option>
          </select>
          <input type="number" min={0} step={5000} value={payFrom} onChange={e => setPayFrom(e.target.value)} className="input mt-1 num" aria-label="Ожидания по зарплате, от" />
          {basis === 'gross' && netLine(Number(payFrom) || null, null) && <span className="field-hint">{netLine(Number(payFrom) || null, null)}</span>}
        </label>
        <label>Город
          <select value={city} onChange={e => setCity(e.target.value)} className={select} aria-label="Город">
            <option value="">не указан</option>
            {(opts?.cities ?? []).map((name: string) => <option key={name} value={name}>{name}</option>)}
          </select>
          <span className="field-hint">Фильтр выдачи. В оценку соответствия не входит.</span>
        </label>
        <fieldset>
          <legend>Формат работы</legend>
          <div className="mt-1 flex flex-wrap gap-3">
            {entries(opts?.work_formats).map(([k, v]) => (
              <label key={k} className="flex items-center gap-2">
                <input type="checkbox" checked={formats.includes(k)} onChange={() => setFormats(prev => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k])} />
                {v}
              </label>
            ))}
          </div>
          <span className="field-hint">Пустой список не отсекает вас из поиска.</span>
        </fieldset>
        <label>Ожидания по зарплате, до
          <input type="number" min={0} step={5000} value={payTo} onChange={e => setPayTo(e.target.value)} className="input mt-1 num" placeholder="до НДФЛ" />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => save.mutate()} disabled={!spec || !grade || save.isPending} className="btn-primary text-sm">
          {save.isPending ? 'Сохраняем…' : 'Сохранить опрос'}
        </button>
        {note && <span className="text-sm text-ink-2" role="status">{note}</span>}
      </div>
    </div>
  )
}
