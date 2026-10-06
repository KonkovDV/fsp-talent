import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, ClipboardCheck, Clock, Lock, XCircle } from 'lucide-react'
import {
  abandonAssessment, activeAssessment, answerAssessment, apiError, assessmentBlueprint, assessmentHistory,
  getMyProfile, reviewAssessment, startAssessment,
} from '../../api/client'
import SurveyCard from '../../components/SurveyCard'
import { Meter, PageHeader, plural } from '../../components/ui'

import { GRADES, gradeRu } from '../../labels'

interface Item {
  token: string; seq: number; stem: string; code: string | null; language: string | null
  answer_mode: 'choice' | 'number'
  options: { index: number; text: string }[]; topic_label: string; family_title: string; kind: string
  time_limit_s: number; served_at: string
}
interface ReviewItem {
  seq: number; stem: string; code: string | null; answer_mode: 'choice' | 'number'; options: string[]
  your_answer: number | null; your_text: string | null; right_answer: number | null; right_text: string | null
  correct: boolean | null; explanation: string | null; topic_label: string
}
const WHOLE = /^[+\-\u2212]?\d{1,12}$/
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
  const [params] = useSearchParams()
  const vacancyId = params.get('vacancy')
  const [target, setTarget] = useState('')
  const [lang, setLang] = useState('python')
  const [state, setState] = useState<SessionState | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState('')
  const [showReview, setShowReview] = useState(false)

  const { data: profile } = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const { data: blueprint } = useQuery({ queryKey: ['blueprint'], queryFn: () => assessmentBlueprint().then(r => r.data) })
  const { data: history } = useQuery({ queryKey: ['assessmentHistory'], queryFn: () => assessmentHistory().then(r => r.data) })
  const { data: active } = useQuery({
    queryKey: ['assessmentActive'], queryFn: () => activeAssessment().then(r => r.data).catch(() => null), retry: false,
  })
  useEffect(() => { if (active && !state) setState(active) }, [active, state])
  // Preselect a sensible level so «Начать тест» is never a dead button: the declared grade, else the category grade.
  useEffect(() => {
    if (!profile || target) return
    const order = [...GRADES]
    const base = profile.declared_grade ?? profile.grade ?? (profile.work_goal === 'internship' ? 'intern' : 'junior')
    const next = profile.grade_source === 'assessed'
      ? order[Math.min(Math.max(order.indexOf(profile.grade), 0) + 1, order.length - 1)]
      : base
    setTarget(order.includes(next) ? next : 'junior')
  }, [profile, target])

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
    mutationFn: () => startAssessment({ target_grade: target, code_language: lang, vacancy_id: vacancyId }).then(r => r.data),
    onSuccess: (data: SessionState) => { setState(data); setPicked(null); setTyped(''); setError(''); setShowReview(false) },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось начать тест')),
  })
  const answer = useMutation({
    mutationFn: () => answerAssessment(state!.session_id, state!.item!.token,
      state!.item!.answer_mode === 'number' ? { answer_text: typed.replace(/\s/g, '') } : { answer_index: picked! },
    ).then(r => r.data),
    onSuccess: (data: SessionState) => { setState(data); setPicked(null); setTyped(''); if (data.result) refresh() },
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

  if (!profile) return <div className="animate-pulse h-64 bg-sunken rounded-2xl" />
  const item = state?.item
  const result = state?.result
  const ready = item?.answer_mode === 'number' ? WHOLE.test(typed.replace(/\s/g, '')) : picked !== null

  return (
    <div className="space-y-6">
      <PageHeader title="Тест на грейд" lead="Адаптивный: задания по одному, сложность подстраивается под ответы. Задания собираются заново для каждого кандидата, ответы проверяет код." />

      {!spec && <SurveyCard profile={profile} />}

      {spec && !item && !result && (
        <div className="grid items-start gap-6 lg:grid-cols-[1.3fr_1fr]">
          <div className="card space-y-6">
            <div>
              <p className="text-xs text-ink-3">Специализация из опроса</p>
              <p className="mt-1 text-lg font-semibold text-ink">{plan?.label ?? spec}</p>
              <p className="mt-1 text-sm text-ink-2">Подтверждённый грейд: <b className="text-ink">{confirmation?.grade ? gradeRu(confirmation.grade) : 'пока нет'}</b>
                {confirmation?.locked_until && <>, повышение после {new Date(confirmation.locked_until).toLocaleDateString('ru-RU')}</>}</p>
            </div>
            <fieldset>
              <legend className="field-label">Какой уровень подтвердить</legend>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5" role="radiogroup" aria-label="Уровень">
                {GRADES.map(g => (
                  <button key={g} type="button" role="radio" aria-checked={target === g} onClick={() => setTarget(g)}
                    className={`rounded-lg border px-3 py-3 text-center transition-colors ${target === g ? 'border-accent bg-accent-soft' : 'border-line-strong bg-panel hover:border-accent/60'}`}>
                    <span className="block font-display text-sm font-bold text-ink">{gradeRu(g)}</span>
                    {confirmation?.grade === g && <span className="text-2xs text-ok">подтверждён</span>}
                  </button>
                ))}
              </div>
              <p className="field-hint">Уверенный результат поднимет грейд на ступень выше выбранного.</p>
            </fieldset>
            <fieldset>
              <legend className="field-label">Язык в заданиях на чтение кода</legend>
              <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Язык кода">
                {Object.entries((blueprint?.code_languages ?? { python: 'Python' }) as Record<string, string>).map(([k, v]) => (
                  <button key={k} type="button" role="radio" aria-checked={lang === k} onClick={() => setLang(k)}
                    className={`rounded-full border px-3.5 py-1.5 text-sm ${lang === k ? 'border-accent bg-accent-soft font-medium text-accent' : 'border-line-strong text-ink-2 hover:border-accent/60'}`}>{v}</button>
                ))}
              </div>
              <p className="field-hint">Задания на подсчёт операций будут на выбранном языке; остальные зависят от темы (SQL, JavaScript, сети).</p>
            </fieldset>
            {vacancyId && <p className="text-sm text-ink-2">Темы этого теста собраны из выбранной вакансии, а не из общего плана специализации.</p>}
            <button onClick={() => start.mutate()} disabled={!target || start.isPending} className="btn-primary px-6 py-3">
              <ClipboardCheck size={16} aria-hidden />{start.isPending ? 'Готовим задания…' : 'Начать тест'}
            </button>
          </div>
          <aside className="card space-y-4">
            <h2 className="section-title">Из чего состоит тест</h2>
            {plan && (
              <>
                <div className="flex h-2.5 overflow-hidden rounded-full" aria-hidden>
                  {plan.topics.map((t: { topic: string; share: number }, i: number) => (
                    <span key={t.topic} style={{ width: `${t.share * 100}%`, opacity: 1 - i * 0.14 }} className="bg-accent first:rounded-l-full last:rounded-r-full [&:not(:last-child)]:mr-0.5" />
                  ))}
                </div>
                <ul className="space-y-1.5 text-sm">
                  {plan.topics.map((t: { topic: string; label: string; share: number }) => (
                    <li key={t.topic} className="flex justify-between"><span className="text-ink">{t.label}</span><span className="num text-ink-2">{Math.round(t.share * 100)} %</span></li>
                  ))}
                </ul>
              </>
            )}
            <ul className="space-y-1.5 border-t border-line pt-4 text-sm text-ink-2">
              <li>{blueprint?.min_items}–{blueprint?.max_items} заданий, тест заканчивается, как только результат ясен.</li>
              <li>3 минуты на задание с кодом, 75 секунд на вопрос.</li>
              <li>Если ответ на задание с кодом — целое число, его вводят сами: вариантов нет, угадать нельзя.</li>
              <li>Уровень подтверждается при вероятности не ниже {pct(blueprint?.pass_probability)}, повышение — при {pct(blueprint?.upgrade_probability)}.</li>
              <li>Пересдача того же уровня — через 7 дней. Прерванная попытка засчитывается.</li>
            </ul>
          </aside>
        </div>
      )}

      {item && state && (
        <div className="card mx-auto max-w-3xl space-y-5" data-testid="assessment-item">
          <div className="flex items-center justify-between text-xs text-ink-3">
            <span>Задание {item.seq}. {item.family_title.toLowerCase().startsWith(item.topic_label.toLowerCase()) ? item.family_title : `${item.topic_label}: ${item.family_title}`}</span>
            <span className={`flex items-center gap-1 font-mono ${left < 20 ? 'text-invite' : ''}`}>
              <Clock size={12} />{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
            </span>
          </div>
          <div className="h-1.5 bg-sunken rounded-full overflow-hidden" aria-hidden>
            <div className="h-full bg-accent" style={{ width: `${Math.min(100, (state.progress.answered / state.progress.max_items) * 100)}%` }} />
          </div>
          <p className={`whitespace-pre-wrap text-sm leading-relaxed ${item.stem.includes(" | ") ? "font-mono" : ""}`}>{item.stem}</p>
          {item.code && (
            <pre className="code-block"><code>{item.code}</code></pre>
          )}
          {item.answer_mode === 'number' ? (
            <form onSubmit={e => { e.preventDefault(); if (ready && !answer.isPending) answer.mutate() }}>
              <label htmlFor="typed-answer" className="field-label">Ответ — целое число</label>
              <input id="typed-answer" key={item.token} value={typed} onChange={e => setTyped(e.target.value)} autoFocus
                inputMode="numeric" autoComplete="off" spellCheck={false} maxLength={32} placeholder="например, 42"
                className="input max-w-xs font-mono text-base" aria-describedby="typed-hint" />
              <p id="typed-hint" className="field-hint">Вариантов в этом задании нет. Enter отправляет ответ.</p>
            </form>
          ) : (
            <div className="grid gap-2" role="radiogroup">
              {item.options.map(o => (
                <button key={o.index} role="radio" aria-checked={picked === o.index} onClick={() => setPicked(o.index)}
                  className={`text-left px-4 py-3 rounded-xl border font-mono text-sm ${picked === o.index ? 'border-accent bg-accent-soft' : 'border-border hover:border-accent/50'}`}>
                  {o.text}
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between">
            <button onClick={() => { if (window.confirm('Прервать тест? Попытка засчитается, пересдача — через 7 дней.')) stop.mutate() }}
              className="text-sm text-ink-3 hover:text-invite">Прервать</button>
            <button onClick={() => answer.mutate()} disabled={!ready || answer.isPending} className="btn-primary">
              {answer.isPending ? 'Проверяем…' : 'Ответить'}
            </button>
          </div>
          <p className="text-xs text-ink-3">Ответ нельзя изменить. Отвечено: {state.progress.answered}, тест закончится не раньше {state.progress.min_items}-го и не позже {state.progress.max_items}-го задания.</p>
        </div>
      )}

      {result && state && (
        <div className="card mx-auto max-w-3xl space-y-5" data-testid="assessment-result">
          <div className={result.passed ? 'hero-ink -m-5 mb-0 p-6 sm:-m-6 sm:mb-0 sm:p-8' : 'flex items-start gap-3'}>
            {result.passed ? (
              <>
                <p className="flex items-center gap-2 text-sm on-hero-muted"><CheckCircle2 size={18} aria-hidden /> Уровень подтверждён{result.upgraded ? ' с повышением на ступень' : ''}</p>
                <p className="mt-3 font-display font-bold leading-none tracking-[-0.04em] [font-size:clamp(3rem,7vw,4.5rem)]">{result.earned_grade}</p>
                <p className="mt-3 max-w-[56ch] text-sm on-hero-muted">{OUTCOME_TEXT[result.outcome] ?? ''}</p>
              </>
            ) : (
              <>
                <XCircle className="shrink-0 text-invite" aria-hidden />
                <div>
                  <p className="section-title">Уровень {state.target_grade} не подтверждён</p>
                  <p className="text-sm text-ink-2">{OUTCOME_TEXT[result.outcome] ?? ''}</p>
                </div>
              </>
            )}
          </div>
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="stat-card"><dt className="stat-card-label">Вероятность уровня {state.target_grade}</dt><dd className="stat-card-value">{pct(result.p_pass)}</dd></div>
            <div className="stat-card"><dt className="stat-card-label">Заданий, из них верно</dt><dd className="stat-card-value">{result.items_count}<span className="text-base text-ink-3">, {pct(result.score)}</span></dd></div>
            <div className="stat-card"><dt className="stat-card-label">Оценка способности θ</dt><dd className="stat-card-value">{result.theta.toFixed(2)}<span className="text-base text-ink-3"> ± {result.se.toFixed(2)}</span></dd></div>
          </dl>
          {result.topics.length > 0 && (
            <ul className="grid gap-3 sm:grid-cols-2" aria-label="Результат по темам">
              {result.topics.map(t => (
                <li key={t.topic}>
                  <div className="flex justify-between text-sm"><span className="text-ink">{t.label}</span><span className="num text-ink-2">{t.correct} из {t.answered}</span></div>
                  <div className="mt-1.5"><Meter value={t.answered ? t.correct / t.answered : 0} ariaLabel={`${t.label}: ${t.correct} из ${t.answered}`} /></div>
                </li>
              ))}
            </ul>
          )}
          {(() => {
            const weak = result.topics.filter(t => t.answered > 0).sort((a, b) => a.correct / a.answered - b.correct / b.answered)[0]
            if (!weak || weak.correct >= weak.answered) return null
            return <p className="text-sm">Слабее всего {weak.label}: {weak.correct} из {weak.answered}. <Link className="text-accent" to={`/candidate/vacancies?topic=${weak.topic}`}>Короткая практика по этой теме</Link> грейд не меняет.</p>
          })()}
          {result.confirmed_skills.length > 0 && (
            <p className="text-sm">Навыки, подтверждённые тестом: {result.confirmed_skills.map(s => `${s.name} (${pct(s.share)})`).join(', ')}.
              <span className="text-ink-3"> В поиске они весят больше заявленных.</span></p>
          )}
          {result.excluded_items > 0 && <p className="text-xs text-ink-3">{result.excluded_items} {plural(result.excluded_items, ['задание исключено', 'задания исключены', 'заданий исключены'])} из оценки: по ним замечены признаки утечки.</p>}
          <div className="flex gap-3">
            <button onClick={() => setShowReview(v => !v)} className="btn-secondary text-sm">{showReview ? 'Скрыть разбор' : 'Разбор заданий'}</button>
            <button onClick={() => { setState(null); setShowReview(false) }} className="btn-secondary text-sm">К тестам</button>
          </div>
          {showReview && review.data && (
            <ol className="space-y-3 text-sm">
              {(review.data.items as ReviewItem[]).map(r => (
                <li key={r.seq} className="border border-border rounded-xl p-3 space-y-1">
                  <p className="text-xs text-ink-3">{r.seq}. {r.topic_label}, {r.correct ? 'верно' : 'неверно'}</p>
                  <p className={`whitespace-pre-wrap ${r.stem.includes(" | ") ? "font-mono text-xs" : ""}`}>{r.stem}</p>
                  {r.code && <pre className="bg-sunken rounded p-2 text-xs overflow-x-auto">{r.code}</pre>}
                  {r.answer_mode === 'number'
                    ? <p className="text-xs">Ваш ответ: <span className="font-mono">{r.your_text ?? '—'}</span>, правильный: <b className="font-mono">{r.right_text}</b></p>
                    : <p className="text-xs">Ваш ответ: {r.your_answer == null ? '—' : r.options[r.your_answer]}
                        {r.right_answer != null && <>, правильный: <b>{r.options[r.right_answer]}</b></>}</p>}
                  {r.explanation && <p className="text-xs text-ink-2">{r.explanation}</p>}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {error && <p className="notice-error" role="alert"><Lock size={14} className="mt-0.5 shrink-0" aria-hidden />{error}</p>}

      {(history?.items ?? []).length > 0 && (
        <div className="card">
          <p className="font-semibold mb-2 text-sm">История</p>
          <ul className="text-sm divide-y divide-border">
            {(history.items as HistoryItem[]).map(h => (
              <li key={h.session_id} className="py-2 flex justify-between gap-2">
                <span>{new Date(h.started_at).toLocaleDateString('ru-RU')}, {h.specialization ?? '—'}, {h.target_grade}</span>
                <span className="text-ink-3">{h.status === 'completed' ? (h.grade_assigned ?? 'не подтверждён') : h.status}
                  {h.p_pass != null && `, ${pct(h.p_pass)}`}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
