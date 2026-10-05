import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks } from 'lucide-react'
import { apiError, saveSurvey, surveyOptions } from '../api/client'

export interface SurveyHint {
  specialization?: string
  declared_grade?: string
  experience_years?: number
  nonce: number
}

interface Props {
  profile: { specialization: string | null; industry: string | null; work_goal: string | null
    declared_grade: string | null; experience_years: number | null; survey_done: boolean }
  compact?: boolean
  hint?: SurveyHint | null
}

/** TZ 2.1: specialization and industry from the survey + declared grade + test make the category. */
export default function SurveyCard({ profile, compact, hint }: Props) {
  const qc = useQueryClient()
  const { data: opts } = useQuery({ queryKey: ['surveyOptions'], queryFn: () => surveyOptions().then(r => r.data) })
  const [spec, setSpec] = useState(profile.specialization ?? '')
  const [industry, setIndustry] = useState(profile.industry ?? '')
  const [goal, setGoal] = useState(profile.work_goal ?? 'job')
  const [grade, setGrade] = useState(profile.declared_grade ?? '')
  const [years, setYears] = useState(profile.experience_years == null ? '' : String(profile.experience_years))
  const [note, setNote] = useState('')
  useEffect(() => {
    setSpec(profile.specialization ?? ''); setIndustry(profile.industry ?? '')
    setGoal(profile.work_goal ?? 'job'); setGrade(profile.declared_grade ?? '')
  }, [profile.specialization, profile.industry, profile.work_goal, profile.declared_grade])
  useEffect(() => {
    if (!hint) return
    if (hint.specialization) setSpec(hint.specialization)
    if (hint.declared_grade) setGrade(hint.declared_grade)
    if (hint.experience_years != null) setYears(String(hint.experience_years))
  }, [hint])

  const save = useMutation({
    mutationFn: () => saveSurvey({ specialization: spec, industry, work_goal: goal, declared_grade: grade || null,
      experience_years: years === '' ? null : Number(years) }),
    onSuccess: () => { setNote('Сохранено. Категория пересчитана.'); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: (e: unknown) => setNote(apiError(e)),
  })
  const select = 'select mt-1'
  const entries = (o?: Record<string, string>) => Object.entries(o ?? {})

  return (
    <div className="card space-y-3" data-testid="survey">
      <div className="flex items-start gap-3">
        <ListChecks className="text-accent shrink-0 mt-0.5" size={20} />
        <div>
          <p className="section-title">{profile.survey_done ? 'Опрос' : 'Шаг 1. Короткий опрос'}</p>
          {!compact && <p className="text-sm text-text-secondary">Специализация задаёт категорию и состав теста:
            задания из других направлений в ваш тест не попадут. Грейд подтверждается отдельно для каждой специализации.</p>}
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <label>Специализация
          <select value={spec} onChange={e => setSpec(e.target.value)} className={select} aria-label="Специализация">
            <option value="">выберите</option>
            {entries(opts?.specializations).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Отрасль
          <select value={industry} onChange={e => setIndustry(e.target.value)} className={select} aria-label="Отрасль">
            <option value="">выберите</option>
            {entries(opts?.industries).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Что ищете
          <select value={goal} onChange={e => setGoal(e.target.value)} className={select}>
            {entries(opts?.work_goals).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label>Ваш грейд (заявленный)
          <select value={grade} onChange={e => setGrade(e.target.value)} className={select}>
            <option value="">не указан</option>
            {(opts?.grades ?? []).map((g: string) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        <label>Опыт, лет
          <input type="number" min={0} max={50} value={years} onChange={e => setYears(e.target.value)} className="input mt-1" />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={() => save.mutate()} disabled={!spec || !industry || save.isPending} className="btn-primary text-sm">
          {save.isPending ? 'Сохраняем…' : 'Сохранить опрос'}
        </button>
        {note && <span className="text-sm text-text-secondary" role="status">{note}</span>}
      </div>
    </div>
  )
}
