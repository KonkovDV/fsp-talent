import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { CheckCircle2, ClipboardCheck, Clock, Info, Lock, XCircle } from 'lucide-react'
import {
  abandonAssessment, activeAssessment, answerAssessment, apiError, assessmentBlueprint, assessmentHistory,
  getMyProfile, reviewAssessment, startAssessment,
} from '../../api/client'
import SurveyCard from '../../components/SurveyCard'
import { Meter, PageHeader, plural } from '../../components/ui'

import { GRADES, ROLE_RU, SESSION_STATUS_RU, gradeRu } from '../../labels'

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
  vacancy_test: boolean; recommended_grade: string | null
  p_pass: number; p_upgrade: number | null; theta: number; se: number; items_count: number; score: number
  stop_reason: string | null; grade_locked_until: string | null; trial?: boolean; note?: string | null
  confirmed_skills: { name: string; share: number }[]
  topics: { topic: string; label: string; answered: number; correct: number; wilson_low?: number | null }[]
  excluded_items: number
  person_fit?: { lz_star: number; review: boolean } | null
  family_review?: boolean
}
interface SessionState {
  session_id: string; status: string; specialization: string | null; target_grade: string; expires_at: string
  progress: { answered: number; min_items: number; max_items: number; p_pass?: number | null; theta?: number | null; se?: number | null }
  item: Item | null; result: Result | null
}
interface HistoryItem {
  session_id: string; status: string; specialization: string | null; target_grade: string
  grade_assigned: string | null; p_pass: number | null; items_count: number | null; started_at: string
  vacancy_test?: boolean; trial?: boolean
}

const OUTCOME_TEXT: Record<string, string> = {
  first_confirmation: 'Грейд подтверждён. Работодатели видят его с отметкой «подтверждён тестом».',
  upgrade: 'Грейд повышен. Следующее повышение в этой специализации — через 90 дней.',
  trial: 'Пробный проход: грейд не подтверждается и в поиске не учитывается.',
  confirmed_again: 'Результат совпал с уже подтверждённым грейдом. Профиль не изменился.',
  kept_higher_grade: 'У вас уже подтверждён более высокий грейд. Тест его не понижает.',
  not_passed: 'Заявленный уровень не подтверждён. Профиль не изменился. Тест на уровень ниже можно пройти сразу, ждать не нужно.',
  vacancy_test: 'Это тест по вакансии: он показывает результат по темам вакансии и подтверждает навыки, но грейд не меняет. Грейд даёт только основной тест специализации.',
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
  const [params, setParams] = useSearchParams()
  const vacancyId = params.get('vacancy')
  const [target, setTarget] = useState('')
  const levelTouched = useRef(false)
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
    if (!profile || levelTouched.current) return
    const order = [...GRADES]
    const base = (profile.grade_source === 'assessed' ? profile.grade : null)
      ?? profile.declared_grade ?? profile.grade ?? (profile.work_goal === 'internship' ? 'intern' : 'junior')
    setTarget(order.includes(base) ? base : 'junior')
  }, [profile])

  const spec: string | null = profile?.specialization ?? null
  const plan = spec && blueprint ? blueprint.specializations[spec] : null
  const confirmation = useMemo(
    () => (profile?.confirmations ?? []).find((c: { specialization: string }) => c.specialization === spec),
    [profile, spec])
  const left = useCountdown(state?.item ?? null)

  const refresh = () => {
    for (const key of ['myProfile', 'assessmentHistory', 'assessmentActive']) qc.invalidateQueries({ queryKey: [key] })
  }
  const startKey = useRef<{ sig: string; key: string } | null>(null)
  const start = useMutation({
    mutationFn: (mode: 'grade' | 'express' = 'grade') => {
      const body = { target_grade: target, code_language: lang, mode, vacancy_id: mode === 'grade' ? vacancyId : null }
      const sig = JSON.stringify(body)
      if (!startKey.current || startKey.current.sig !== sig) startKey.current = { sig, key: crypto.randomUUID() }
      return startAssessment(body, startKey.current.key).then(r => r.data)
    },
    onSuccess: (data: SessionState) => { startKey.current = null; setState(data); setPicked(null); setTyped(''); setError(''); setShowReview(false) },
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
                  <button key={g} type="button" role="radio" aria-checked={target === g} onClick={() => { levelTouched.current = true; setTarget(g) }}
                    className={`rounded-lg border px-3 py-3 text-center transition-colors ${target === g ? 'border-accent bg-accent-soft' : 'border-line-strong bg-panel hover:border-accent/60'}`}>
                    <span className="block font-display text-sm font-bold text-ink">{gradeRu(g)}</span>
                    {confirmation?.grade === g && <span className="text-2xs text-ok">подтверждён</span>}
                  </button>
                ))}
              </div>
              <p className="field-hint">Тест подтверждает только выбранный уровень. Если результат уверенно выше, предложим отдельный тест на следующий. После подтверждения следующий уровень ждёт 90 дней, уровень ниже доступен сразу.</p>
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
            {vacancyId && <p className="text-sm text-ink-2">Темы этого теста собраны из выбранной вакансии, а не из общего плана специализации. Тест по вакансии грейд не меняет: покажет результат по темам и подтвердит навыки, а грейд даёт только основной тест.</p>}
            <div className="flex flex-wrap gap-3">
              <button onClick={() => start.mutate('grade')} disabled={!target || start.isPending} className="btn-primary px-6 py-3">
                <ClipboardCheck size={16} aria-hidden />{start.isPending ? 'Готовим задания…' : 'Начать тест'}
              </button>
              {blueprint?.express && !vacancyId && (
                <button onClick={() => start.mutate('express')} disabled={!target || start.isPending} className="btn-secondary px-6 py-3">
                  Пробный тест, {blueprint.express_items ?? 15} заданий, {blueprint.express_minutes ?? 5} минут
                </button>
              )}
            </div>
            {blueprint?.express && !vacancyId && <p className="field-hint">Пробный проход: {blueprint.express_items ?? 15} заданий и {blueprint.express_minutes ?? 5} минут. Грейд не подтверждается и в поиске не учитывается.</p>}
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
              <li>Уровень подтверждается при вероятности не ниже {pct(blueprint?.pass_probability)}. Тест на ступень выше предлагаем при {pct(blueprint?.next_test_probability)}, но грейд сам не повышается.</li>
              <li>Пересдача того же уровня — через 7 дней. Прерванная попытка засчитывается.</li>
              <li>Не сдали — тест на уровень ниже доступен сразу. После смены грейда следующее повышение — через 90 дней.</li>
            </ul>
          </aside>
        </div>
      )}

      {item && state && (
        <div className="card mx-auto max-w-3xl space-y-5" data-testid="assessment-item">
          <div className="flex items-center justify-between text-xs text-ink-3">
            <span>Задание {item.seq}. {item.family_title.toLowerCase().startsWith(item.topic_label.toLowerCase()) ? item.family_title : `${item.topic_label}: ${item.family_title}`}</span>
            <span role="timer" aria-label={`Осталось ${Math.floor(left / 60)} мин ${left % 60} с`}
              className={`flex items-center gap-1 rounded-md px-2 py-1 font-mono text-sm tabular-nums ${left < 20 ? 'bg-danger-soft font-semibold text-danger' : 'bg-sunken text-ink-2'}`}>
              <Clock size={13} aria-hidden />{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
            </span>
          </div>
          {state.progress.answered >= 1 && state.progress.p_pass != null && (
            <ConfidenceScale p={state.progress.p_pass} trial={state.progress.min_items === state.progress.max_items}
              detail={state.progress.se != null ? `θ ${state.progress.theta?.toFixed(2)} ± ${state.progress.se.toFixed(2)}` : ''} />
          )}
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
                  className={`flex min-h-12 items-center gap-3 rounded-lg border px-4 py-3 text-left font-mono text-sm transition-colors ${picked === o.index ? 'border-accent bg-accent-soft text-ink' : 'border-line-strong bg-panel hover:border-accent/60'}`}>
                  <span className={`grid h-4 w-4 shrink-0 place-items-center rounded-full border-2 ${picked === o.index ? 'border-accent' : 'border-field'}`} aria-hidden>
                    {picked === o.index && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}
                  </span>
                  <span className="min-w-0">{o.text}</span>
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between">
            <button onClick={() => {
              const trial = state.progress.min_items === state.progress.max_items
              const warning = trial
                ? 'Прервать пробный проход? Грейд не изменится и паузы перед следующим тестом не будет.'
                : 'Прервать тест? Попытка засчитается, пересдача — через 7 дней.'
              if (window.confirm(warning)) stop.mutate()
            }}
              className="btn-ghost btn-sm -ml-3 text-ink-3 hover:text-danger">Прервать</button>
            <button onClick={() => answer.mutate()} disabled={!ready || answer.isPending} className="btn-primary">
              {answer.isPending ? 'Проверяем…' : 'Ответить'}
            </button>
          </div>
          <p className="text-xs text-ink-3">
            Ответ нельзя изменить. Отвечено: {state.progress.answered}.{' '}
            {state.progress.min_items === state.progress.max_items
              ? `Это пробный проход из ${state.progress.max_items} заданий: шкала уверенности видна, но грейд не меняется.`
              : `Тест закончится, когда уверенность дойдёт до 90 % или упадёт ниже 10 %, не раньше ${state.progress.min_items}-го и не позже ${state.progress.max_items}-го задания.`}
          </p>
        </div>
      )}

      {result && state && (
        <div className="card mx-auto max-w-3xl space-y-5" data-testid="assessment-result">
          {result.trial && <p className="notice" role="status">{result.note || 'Пробный проход: грейд не подтверждается и в поиске не учитывается.'}</p>}
          {result.person_fit?.review && (
            <p className="notice" role="status">Ответы плохо сходятся с оценкой уровня. Это не вывод о списывании: имеет смысл пересдать.</p>
          )}
          {result.family_review && (
            <p className="notice" role="status">По одному семейству доля верных ответов и скорость выбиваются из обычного хода. Грейд из-за этого не меняется.</p>
          )}
          {result.trial ? (
            <div className="flex items-start gap-3" data-testid="trial-verdict">
              <Info className="shrink-0 text-accent" aria-hidden />
              <div>
                <p className="section-title">
                  {result.p_pass >= (blueprint?.pass_probability ?? 0.75)
                    ? `Уровень «${gradeRu(state.target_grade)}» по этим ответам подтвердился бы`
                    : result.p_pass >= 0.5
                      ? `Уровень «${gradeRu(state.target_grade)}» скорее подтвердился бы, но уверенности для решения не хватило`
                      : `Уровень «${gradeRu(state.target_grade)}» по этим ответам пока не подтвердился бы`}
                </p>
                <p className="text-sm text-ink-2">Вероятность уровня {pct(result.p_pass)}. Основной тест подтверждает грейд, когда она доходит до {pct(blueprint?.pass_probability ?? 0.75)}. Пробный проход в профиль и поиск не попадает.</p>
              </div>
            </div>
          ) : (
          <div className={result.passed ? 'hero-ink -m-5 mb-0 p-6 sm:-m-6 sm:mb-0 sm:p-8' : 'flex items-start gap-3'}>
            {result.passed ? (
              <>
                <p className="flex items-center gap-2 text-sm on-hero-muted"><CheckCircle2 size={18} aria-hidden />
                  {result.vacancy_test ? 'Тест по вакансии пройден на уровне' : result.upgraded ? 'Грейд повышен' : 'Уровень подтверждён'}</p>
                <p className="mt-3 font-display font-bold leading-none tracking-[-0.04em] [font-size:clamp(3rem,7vw,4.5rem)]">{gradeRu(result.earned_grade)}</p>
                <p className="mt-3 max-w-[56ch] text-sm on-hero-muted">{OUTCOME_TEXT[result.outcome] ?? ''}</p>
              </>
            ) : (
              <>
                <XCircle className="shrink-0 text-danger" aria-hidden />
                <div>
                  <p className="section-title">Уровень «{gradeRu(state.target_grade)}» не подтверждён</p>
                  <p className="text-sm text-ink-2">{OUTCOME_TEXT[result.outcome] ?? ''}</p>
                </div>
              </>
            )}
          </div>
          )}
          {result.recommended_grade && (
            <div className="notice-info flex-wrap items-center justify-between" data-testid="next-test">
              <p className="text-sm text-ink">
                {result.vacancy_test
                  ? <>Можно пройти основной тест на {gradeRu(result.recommended_grade)}: грейд в профиле даёт только он.</>
                  : <>Результат уверенно выше уровня {gradeRu(state.target_grade)}. Можно пройти тест на {gradeRu(result.recommended_grade)}: грейд сам не повышается, нужен отдельный тест.</>}
                {result.grade_locked_until && !result.vacancy_test && <> Повышение доступно после {new Date(result.grade_locked_until).toLocaleDateString('ru-RU')}.</>}
              </p>
              <button type="button" className="btn-primary btn-sm" onClick={() => {
                levelTouched.current = true; setTarget(result.recommended_grade!); setState(null); setShowReview(false)
                if (vacancyId) setParams({}, { replace: true })
              }}>Выбрать тест на {gradeRu(result.recommended_grade)}</button>
            </div>
          )}
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="stat-card"><dt className="stat-card-label">Вероятность уровня «{gradeRu(state.target_grade)}»</dt><dd className="stat-card-value">{pct(result.p_pass)}</dd></div>
            <div className="stat-card"><dt className="stat-card-label">Заданий, из них верно</dt><dd className="stat-card-value">{result.items_count}<span className="text-base text-ink-3">, {pct(result.score)}</span></dd></div>
            <div className="stat-card"><dt className="stat-card-label">Оценка способности θ</dt><dd className="stat-card-value">{result.theta.toFixed(2)}<span className="text-base text-ink-3"> ± {result.se.toFixed(2)}</span></dd></div>
          </dl>
          {result.topics.length > 0 && (
            <ul className="grid gap-3 sm:grid-cols-2" aria-label="Результат по темам">
              {result.topics.map(t => (
                <li key={t.topic}>
                  <div className="flex justify-between text-sm"><span className="text-ink">{t.label}</span><span className="num text-ink-2">{t.correct} из {t.answered}</span></div>
                  <div className="mt-1.5"><Meter value={t.answered ? t.correct / t.answered : 0} ariaLabel={`${t.label}: ${t.correct} из ${t.answered}`} /></div>
                  {t.wilson_low != null && <p className="mt-1 text-xs text-ink-3">Нижняя граница доли верных {pct(t.wilson_low)}</p>}
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
                <span>{new Date(h.started_at).toLocaleDateString('ru-RU')}, {h.specialization ? (ROLE_RU[h.specialization] ?? h.specialization) : '—'}, {gradeRu(h.target_grade)}{h.vacancy_test ? ', по вакансии' : ''}{h.trial ? ', пробный' : ''}</span>
                <span className="text-ink-3">{h.status === 'completed' ? (h.trial ? 'без решения о грейде' : h.grade_assigned ? `подтверждён: ${gradeRu(h.grade_assigned)}` : 'не подтверждён') : (SESSION_STATUS_RU[h.status] ?? h.status)}
                  {h.p_pass != null && `, ${pct(h.p_pass)}`}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/** Confidence that the level is already clear, with the two stop lines of the adaptive test: 10 % and 90 %. */
function ConfidenceScale({ p, detail, trial }: { p: number; detail: string; trial: boolean }) {
  const v = Math.max(0, Math.min(100, Math.round(p * 100)))
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap justify-between gap-x-3 text-xs text-ink-3">
        <span>Уверенность, что уровень уже ясен</span>
        <span className="num"><span className="font-display font-bold text-ink">{v} %</span>{detail ? ` · ${detail}` : ''}</span>
      </div>
      <div className="relative h-3 rounded-full bg-ink/[0.07] dark:bg-white/[0.08]" role="meter" aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={v} aria-label="Уверенность решения">
        <span className="absolute inset-y-0 left-0 w-[10%] rounded-l-full bg-danger/20" aria-hidden />
        <span className="absolute inset-y-0 right-0 w-[10%] rounded-r-full bg-ok/25" aria-hidden />
        <span className="absolute inset-y-0 left-0 rounded-full bg-accent/80 transition-[width] duration-500" style={{ width: `${v}%` }} aria-hidden />
        <span className="absolute -top-1 h-5 w-1 -translate-x-1/2 rounded-full bg-accent ring-2 ring-panel transition-[left] duration-500" style={{ left: `${v}%` }} aria-hidden />
      </div>
      <div className="mt-1 flex justify-between text-2xs text-ink-3" aria-hidden>
        <span>10 % — не подтвердится</span>
        <span>{trial ? 'пробный проход' : '90 % — подтвердится'}</span>
      </div>
    </div>
  )
}
