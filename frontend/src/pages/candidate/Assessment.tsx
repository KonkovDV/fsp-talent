import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ClipboardCheck, Clock, Lock, XCircle } from 'lucide-react'
import {
  abandonAssessment, activeAssessment, answerAssessment, apiError, assessmentBlueprint, assessmentHistory,
  getMyProfile, reviewAssessment, startAssessment,
} from '../../api/client'
import SurveyCard from '../../components/SurveyCard'

const GRADES = ['junior', 'middle', 'senior', 'lead']

interface Item {
  token: string; seq: number; stem: string; code: string | null; language: string | null
  options: { index: number; text: string }[]; topic_label: string; family_title: string; kind: string
  time_limit_s: number; served_at: string
}
interface Result {
  outcome: string; passed: boolean; upgraded: boolean; earned_grade: string | null; confirmed_grade: string | null
  p_pass: number; p_upgrade: number | null; theta: number; se: number; items_count: number; score: number
  stop_reason: string | null; grade_locked_until: string | null
  confirmed_skills: { name: string; share: number }[]
  topics: { topic: string; label: string; answered: number; correct: number }[]
  excluded_items: number
}
interface SessionState {
  session_id: string; status: string; specialization: string | null; target_grade: string; expires_at: string
  progress: { answered: number; min_items: number; max_items: number }
  item: Item | null; result: Result | null
}
interface HistoryItem {
  session_id: string; status: string; specialization: string | null; target_grade: string
  grade_assigned: string | null; p_pass: number | null; items_count: number | null; started_at: string
}

const OUTCOME_TEXT: Record<string, string> = {
  first_confirmation: 'Грейд подтверждён. Работодатели видят его с отметкой «подтверждён тестом».',
  upgrade: 'Грейд повышен. Следующее повышение в этой специализации — после периода ожидания.',
  confirmed_again: 'Результат совпал с уже подтверждённым грейдом. Профиль не изменился.',
  kept_higher_grade: 'У вас уже подтверждён более высокий грейд. Тест его не понижает.',
  not_passed: 'Заявленный уровень не подтверждён. Профиль не изменился: можно пройти тест на уровень ниже.',
}
const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`)

function useCountdown(item: Item | null) {
  const [left, setLeft] = useState(0)
  useEffect(() => {
    if (!item) return
    const end = new Date(item.served_at).getTime() + item.time_limit_s * 1000
    const tick = () => setLeft(Math.max(0, Math.round((end - Date.now()) / 1000)))
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [item])
  return left
}

export default function CandidateAssessment() {
  const qc = useQueryClient()
  const [target, setTarget] = useState('')
  const [state, setState] = useState<SessionState | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [showReview, setShowReview] = useState(false)

  const { data: profile } = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const { data: blueprint } = useQuery({ queryKey: ['blueprint'], queryFn: () => assessmentBlueprint().then(r => r.data) })
  const { data: history } = useQuery({ queryKey: ['assessmentHistory'], queryFn: () => assessmentHistory().then(r => r.data) })
  const { data: active } = useQuery({
    queryKey: ['assessmentActive'], queryFn: () => activeAssessment().then(r => r.data).catch(() => null), retry: false,
  })
  useEffect(() => { if (active && !state) setState(active) }, [active, state])
  useEffect(() => { if (profile?.declared_grade && !target) setTarget(profile.declared_grade) }, [profile, target])

  const spec: string | null = profile?.specialization ?? null
  const plan = spec && blueprint ? blueprint.specializations[spec] : null
  const confirmation = useMemo(
    () => (profile?.confirmations ?? []).find((c: { specialization: string }) => c.specialization === spec),
    [profile, spec])
  const left = useCountdown(state?.item ?? null)

  const refresh = () => {
    for (const key of ['myProfile', 'assessmentHistory', 'assessmentActive']) qc.invalidateQueries({ queryKey: [key] })
  }
  const start = useMutation({
    mutationFn: () => startAssessment({ target_grade: target }).then(r => r.data),
    onSuccess: (data: SessionState) => { setState(data); setPicked(null); setError(''); setShowReview(false) },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось начать тест')),
  })
  const answer = useMutation({
    mutationFn: () => answerAssessment(state!.session_id, state!.item!.token, picked!).then(r => r.data),
    onSuccess: (data: SessionState) => { setState(data); setPicked(null); if (data.result) refresh() },
    onError: (e: unknown) => { setError(apiError(e, 'Ответ не принят')); refresh() },
  })
  const stop = useMutation({
    mutationFn: () => abandonAssessment(state!.session_id),
    onSuccess: () => { setState(null); refresh() },
  })
  const review = useQuery({
    queryKey: ['review', state?.session_id], enabled: showReview && !!state?.result,
    queryFn: () => reviewAssessment(state!.session_id).then(r => r.data),
  })

  if (!profile) return <div className="animate-pulse h-64 bg-surface-2 rounded-2xl" />
  const item = state?.item
  const result = state?.result

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold">Тест на грейд</h1>
        <p className="text-sm text-text-muted mt-1">
          Адаптивный тест: задания по одному, сложность подстраивается под ответы, тест заканчивается, как только
          результат ясен. Задания генерируются заново для каждого кандидата, ответы проверяются кодом.
        </p>
      </div>

      {!spec && <SurveyCard profile={profile} />}

      {spec && !item && !result && (
        <div className="card space-y-4">
          <div className="text-sm space-y-1">
            <p>Специализация: <b>{plan?.label ?? spec}</b>{' '}
              <span className="text-text-muted">(меняется в опросе в профиле)</span></p>
            <p>Подтверждённый грейд: <b>{confirmation?.grade ?? 'нет'}</b>
              {confirmation?.locked_until && <span className="text-text-muted"> · повышение после {new Date(confirmation.locked_until).toLocaleDateString('ru-RU')}</span>}</p>
          </div>
          {plan && (
            <div className="flex flex-wrap gap-2" aria-label="Состав теста">
              {plan.topics.map((t: { topic: string; label: string; share: number }) => (
                <span key={t.topic} className="text-xs px-2 py-1 rounded-lg bg-fsp-violet/10 text-fsp-violet">
                  {t.label} · {Math.round(t.share * 100)}%
                </span>
              ))}
            </div>
          )}
          <p className="text-xs text-text-muted">
            {blueprint?.min_items}–{blueprint?.max_items} заданий, на задание с кодом 3 минуты, на вопрос 75 секунд.
            Грейд подтверждается, если вероятность уровня не ниже {pct(blueprint?.pass_probability)}; повышение на
            ступень — при {pct(blueprint?.upgrade_probability)}. Пересдача того же уровня — через 7 дней.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">Проверить уровень
              <select value={target} onChange={e => setTarget(e.target.value)}
                className="mt-1 block border border-border rounded-xl px-3 py-2 bg-surface-1" aria-label="Уровень">
                <option value="">выберите</option>
                {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
            <button onClick={() => start.mutate()} disabled={!target || start.isPending} className="btn-primary gap-2">
              <ClipboardCheck size={16} />{start.isPending ? 'Готовим задания…' : 'Начать тест'}
            </button>
          </div>
        </div>
      )}

      {item && state && (
        <div className="card space-y-4" data-testid="assessment-item">
          <div className="flex items-center justify-between text-xs text-text-muted">
            <span>Задание {item.seq} · {item.topic_label} · {item.family_title}</span>
            <span className={`flex items-center gap-1 font-mono ${left < 20 ? 'text-fsp-red' : ''}`}>
              <Clock size={12} />{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
            </span>
          </div>
          <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden" aria-hidden>
            <div className="h-full bg-fsp-violet" style={{ width: `${Math.min(100, (state.progress.answered / state.progress.max_items) * 100)}%` }} />
          </div>
          <p className={`whitespace-pre-wrap text-sm leading-relaxed ${item.stem.includes(" | ") ? "font-mono" : ""}`}>{item.stem}</p>
          {item.code && (
            <pre className="bg-surface-0 text-text-primary border border-border text-sm rounded-xl p-4 overflow-x-auto"><code>{item.code}</code></pre>
          )}
          <div className="grid gap-2" role="radiogroup">
            {item.options.map(o => (
              <button key={o.index} role="radio" aria-checked={picked === o.index} onClick={() => setPicked(o.index)}
                className={`text-left px-4 py-3 rounded-xl border font-mono text-sm ${picked === o.index ? 'border-fsp-violet bg-fsp-violet/10' : 'border-border hover:border-fsp-violet/50'}`}>
                {o.text}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between">
            <button onClick={() => { if (window.confirm('Прервать тест? Попытка засчитается, пересдача — через 7 дней.')) stop.mutate() }}
              className="text-sm text-text-muted hover:text-fsp-red">Прервать</button>
            <button onClick={() => answer.mutate()} disabled={picked === null || answer.isPending} className="btn-primary">
              {answer.isPending ? 'Проверяем…' : 'Ответить'}
            </button>
          </div>
          <p className="text-xs text-text-muted">Ответ нельзя изменить. Отвечено: {state.progress.answered}, тест закончится не раньше {state.progress.min_items}-го и не позже {state.progress.max_items}-го задания.</p>
        </div>
      )}

      {result && state && (
        <div className="card space-y-4" data-testid="assessment-result">
          <div className="flex items-start gap-3">
            {result.passed ? <CheckCircle2 className="text-green-600 shrink-0" /> : <XCircle className="text-fsp-red shrink-0" />}
            <div>
              <p className="font-semibold">{result.passed
                ? `Уровень ${result.earned_grade} подтверждён${result.upgraded ? ' — с повышением на ступень' : ''}`
                : `Уровень ${state.target_grade} не подтверждён`}</p>
              <p className="text-sm text-text-secondary">{OUTCOME_TEXT[result.outcome] ?? ''}</p>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 text-sm">
            <div className="rounded-xl bg-surface-2 p-3"><p className="text-text-muted text-xs">Вероятность уровня {state.target_grade}</p><p className="text-lg font-bold">{pct(result.p_pass)}</p></div>
            <div className="rounded-xl bg-surface-2 p-3"><p className="text-text-muted text-xs">Заданий / верно</p><p className="text-lg font-bold">{result.items_count} / {pct(result.score)}</p></div>
            <div className="rounded-xl bg-surface-2 p-3"><p className="text-text-muted text-xs">Оценка способности θ</p><p className="text-lg font-bold font-mono">{result.theta.toFixed(2)} ± {result.se.toFixed(2)}</p></div>
          </div>
          {result.topics.length > 0 && (
            <ul className="text-sm space-y-1">
              {result.topics.map(t => <li key={t.topic}>{t.label}: {t.correct} из {t.answered}</li>)}
            </ul>
          )}
          {result.confirmed_skills.length > 0 && (
            <p className="text-sm">Навыки, подтверждённые тестом: {result.confirmed_skills.map(s => `${s.name} (${pct(s.share)})`).join(', ')}.
              <span className="text-text-muted"> В поиске они весят больше заявленных.</span></p>
          )}
          {result.excluded_items > 0 && <p className="text-xs text-text-muted">{result.excluded_items} заданий исключены из оценки: по ним замечены признаки утечки.</p>}
          <div className="flex gap-3">
            <button onClick={() => setShowReview(v => !v)} className="btn-secondary text-sm">{showReview ? 'Скрыть разбор' : 'Разбор заданий'}</button>
            <button onClick={() => { setState(null); setShowReview(false) }} className="btn-secondary text-sm">К тестам</button>
          </div>
          {showReview && review.data && (
            <ol className="space-y-3 text-sm">
              {review.data.items.map((r: { seq: number; stem: string; code: string | null; options: string[]; your_answer: number | null; right_answer: number | null; correct: boolean | null; explanation: string | null; topic_label: string }) => (
                <li key={r.seq} className="border border-border rounded-xl p-3 space-y-1">
                  <p className="text-xs text-text-muted">{r.seq}. {r.topic_label} · {r.correct ? 'верно' : 'неверно'}</p>
                  <p className={`whitespace-pre-wrap ${r.stem.includes(" | ") ? "font-mono text-xs" : ""}`}>{r.stem}</p>
                  {r.code && <pre className="bg-surface-2 rounded p-2 text-xs overflow-x-auto">{r.code}</pre>}
                  <p className="text-xs">Ваш ответ: {r.your_answer == null ? '—' : r.options[r.your_answer]}
                    {r.right_answer != null && <> · правильный: <b>{r.options[r.right_answer]}</b></>}</p>
                  {r.explanation && <p className="text-xs text-text-secondary">{r.explanation}</p>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {error && <p className="text-fsp-red text-sm bg-fsp-red/10 rounded-lg px-4 py-2 flex items-center gap-2" role="alert"><Lock size={14} />{error}</p>}

      {(history?.items ?? []).length > 0 && (
        <div className="card">
          <p className="font-semibold mb-2 text-sm">История</p>
          <ul className="text-sm divide-y divide-border">
            {(history.items as HistoryItem[]).map(h => (
              <li key={h.session_id} className="py-2 flex justify-between gap-2">
                <span>{new Date(h.started_at).toLocaleDateString('ru-RU')} · {h.specialization ?? '—'} · {h.target_grade}</span>
                <span className="text-text-muted">{h.status === 'completed' ? (h.grade_assigned ?? 'не подтверждён') : h.status}
                  {h.p_pass != null && ` · ${pct(h.p_pass)}`}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
