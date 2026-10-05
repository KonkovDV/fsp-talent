import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardCheck, Lock } from 'lucide-react'
import {
  apiError, assessmentCooldown, assessmentHistory, getMyProfile, startAssessment, submitAssessment,
} from '../../api/client'
import { ROLE_RU } from '../../labels'

const SPECIALIZATIONS = ['backend', 'frontend', 'fullstack', 'ml', 'devops', 'security', 'embedded', 'mobile']
const GRADES = ['junior', 'middle', 'senior', 'lead']

interface Option { id: string; text: string }
interface Question { id: string; question_text: string; options: Option[] | null }
interface Session { session_id: string; expires_at: string; target_grade: string; questions: Question[] }
interface Result {
  score: number | null
  grade_assigned: string | null
  confirmed_grade: string | null
  outcome: string
  grade_locked_until: string | null
}
interface HistoryItem {
  session_id: string; status: string; target_grade: string; grade_assigned: string | null
  score: number | null; started_at: string
}

const OUTCOME_TEXT: Record<string, string> = {
  first_confirmation: 'Грейд подтверждён. Работодатели видят его с отметкой «подтверждён тестом».',
  upgrade: 'Грейд повышен. Следующая смена грейда станет доступна после периода ожидания.',
  confirmed_again: 'Результат совпал с уже подтверждённым грейдом. Профиль не изменился.',
  kept_higher_grade: 'У вас уже подтверждён более высокий грейд. Тест его не понижает.',
  not_passed: 'Заявленный уровень не подтверждён. Профиль не изменился: можно пройти тест на уровень ниже.',
}

const fmt = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString('ru-RU') : '—')

export default function CandidateAssessment() {
  const qc = useQueryClient()
  const [specialization, setSpecialization] = useState('')
  const [target, setTarget] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')

  const { data: profile } = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const { data: cooldown } = useQuery({ queryKey: ['assessmentCooldown'], queryFn: () => assessmentCooldown().then(r => r.data) })
  const { data: history } = useQuery({ queryKey: ['assessmentHistory'], queryFn: () => assessmentHistory().then(r => r.data) })

  const start = useMutation({
    mutationFn: () => startAssessment({ target_grade: target, discipline: specialization || null }).then(r => r.data),
    onSuccess: (data: Session) => { setSession(data); setAnswers({}); setResult(null); setError('') },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось начать тест')),
  })
  const submit = useMutation({
    mutationFn: () => submitAssessment(
      session!.session_id,
      Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })),
    ).then(r => r.data),
    onSuccess: (data: Result) => {
      setResult(data); setSession(null); setError('')
      for (const key of ['myProfile', 'assessmentCooldown', 'assessmentHistory']) qc.invalidateQueries({ queryKey: [key] })
    },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось отправить ответы')),
  })

  const answered = session ? session.questions.filter(q => answers[q.id]).length : 0
  const locked = Boolean(cooldown?.locked)

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Тест на грейд</h1>
        <p className="text-sm text-text-muted mt-1">
          Работодатель видит категорию «специализация × грейд». Грейд, подтверждённый тестом, стоит в выдаче
          выше самооценки. Тест не понижает уже подтверждённый грейд.
        </p>
      </div>

      <div className="card space-y-1 text-sm">
        <p>
          Сейчас: <strong>{ROLE_RU[profile?.primary_role ?? ''] ?? profile?.primary_role ?? '—'}</strong> ·{' '}
          <strong>{profile?.grade ?? '—'}</strong>{' '}
          <span className="text-text-muted">
            ({profile?.grade_source === 'assessed' ? 'подтверждён тестом' : 'не подтверждён тестом'})
          </span>
        </p>
        {locked && (
          <p className="flex items-center gap-1.5 text-text-muted">
            <Lock size={13} aria-hidden /> Смена грейда снова доступна {fmt(cooldown?.locked_until)}
          </p>
        )}
      </div>

      {!session && (
        <div className="card space-y-4">
          <p className="font-semibold">1. Опрос: специализация и заявленный грейд</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <label className="text-sm">Специализация
              <select value={specialization} onChange={e => setSpecialization(e.target.value)} className="select mt-1">
                <option value="">Выберите</option>
                {SPECIALIZATIONS.map(s => <option key={s} value={s}>{ROLE_RU[s] ?? s}</option>)}
              </select>
            </label>
            <label className="text-sm">Заявленный грейд
              <select value={target} onChange={e => setTarget(e.target.value)} className="select mt-1">
                <option value="">Выберите</option>
                {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
          </div>
          <p className="text-xs text-text-muted">
            30 минут, вопросы с выбором ответа. Пропущенный вопрос считается неверным. Уверенный результат может
            поднять грейд на один уровень выше заявленного.
          </p>
          <button onClick={() => start.mutate()} disabled={!specialization || !target || locked || start.isPending}
            className="btn-primary text-sm gap-1.5">
            <ClipboardCheck size={14} aria-hidden /> {start.isPending ? 'Готовим вопросы…' : 'Начать тест'}
          </button>
        </div>
      )}

      {session && (
        <div className="space-y-4">
          <p className="text-sm text-text-muted">
            2. Тест на {session.target_grade} · ответов {answered} из {session.questions.length} · до {fmt(session.expires_at)}
          </p>
          {session.questions.map((q, i) => (
            <fieldset key={q.id} className="card space-y-2">
              <legend className="font-semibold text-sm">{i + 1}. {q.question_text}</legend>
              {(q.options ?? []).map(o => (
                <label key={o.id} className="flex items-start gap-2 text-sm cursor-pointer">
                  <input type="radio" name={q.id} value={o.id} checked={answers[q.id] === o.id}
                    onChange={() => setAnswers(a => ({ ...a, [q.id]: o.id }))} className="mt-1" />
                  <span>{o.text}</span>
                </label>
              ))}
            </fieldset>
          ))}
          <button onClick={() => submit.mutate()} disabled={submit.isPending} className="btn-primary text-sm">
            {submit.isPending ? 'Проверяем…' : answered < session.questions.length
              ? `Отправить (без ответа: ${session.questions.length - answered})` : 'Отправить ответы'}
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-600" role="alert">{error}</p>}

      {result && (
        <div className="card space-y-1 text-sm" role="status">
          <p className="font-semibold">3. Результат</p>
          <p>Верных ответов: {Math.round((result.score ?? 0) * 100)}%</p>
          <p>Уровень по результату: <strong>{result.grade_assigned ?? 'не подтверждён'}</strong></p>
          <p>Грейд в профиле: <strong>{result.confirmed_grade ?? 'не подтверждён'}</strong></p>
          <p className="text-text-muted">{OUTCOME_TEXT[result.outcome] ?? result.outcome}</p>
        </div>
      )}

      {(history?.items?.length ?? 0) > 0 && (
        <div className="card">
          <p className="font-semibold text-sm mb-2">История попыток</p>
          <ul className="text-sm space-y-1">
            {history.items.map((h: HistoryItem) => (
              <li key={h.session_id} className="flex justify-between gap-3">
                <span>{fmt(h.started_at)} · тест на {h.target_grade}</span>
                <span className="text-text-muted">
                  {h.status === 'completed'
                    ? `${Math.round((h.score ?? 0) * 100)}% → ${h.grade_assigned ?? 'не подтверждён'}`
                    : h.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
