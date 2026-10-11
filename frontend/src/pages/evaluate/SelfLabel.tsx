import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiError, evaluatePairs, type EvaluateReport } from '../../api/client'
import { plural } from '../../components/ui'

export interface BlindNeed { id: string; role: string; grade: string; skills: string[]; text: string }
export interface BlindPair { pair_id: string; need_id: string; candidate_id: string; card: string; observed: Record<string, unknown> }
export interface BlindSheet { source: string; needs: BlindNeed[]; pairs: BlindPair[] }

type Label = 0 | 1 | 2 | 3
type Labels = Record<string, Label>

export const STORAGE_KEY = 'fsp-evaluate:blind-2029'

/** Short captions from the rubric (docs/VALIDATION_MATCHING.md, «Слепая разметка: два ИИ-оценщика»). */
export const SCALE: { value: Label; title: string; hint: string }[] = [
  { value: 0, title: 'Не подходит', hint: 'другая специализация, ключевых навыков нет' },
  { value: 1, title: 'Слабо', hint: 'смежная специализация или грейд сильно ниже, навыки в основном заявлены' },
  { value: 2, title: 'С оговорками', hint: 'грейд на ступень ниже или часть навыков только заявлена' },
  { value: 3, title: 'Подходит полностью', hint: 'специализация и грейд совпадают, ключевые навыки подтверждены' },
]

const METHOD_TITLE: Record<string, string> = {
  full: 'Наша модель',
  keyword: 'По резюме: заявленные навыки и грейд',
  random: 'Случайный порядок',
}

const share = (v: number | undefined | null) => (v === undefined || v === null ? '—' : v.toFixed(2).replace('.', ','))
const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${share(Math.abs(v))}`

interface Saved { needId: string | null; labels: Labels }

function load(): Saved {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return { needId: null, labels: {} }
    const data = JSON.parse(raw) as Partial<Saved>
    const labels: Labels = {}
    for (const [id, v] of Object.entries(data.labels ?? {})) if (v === 0 || v === 1 || v === 2 || v === 3) labels[id] = v
    return { needId: typeof data.needId === 'string' ? data.needId : null, labels }
  } catch {
    return { needId: null, labels: {} }
  }
}

function save(state: Saved) {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch { /* private mode: labels live until reload */ }
}

/** True when at least one pair is rated 2 or 3: the minimum the backend needs to score. */
export const hasRelevant = (labels: Labels) => Object.values(labels).some(v => v >= 2)

/** The same JSONL the upload mode takes: the backend does all the maths. */
export function toJsonl(sheet: BlindSheet, labels: Labels): string {
  const needs = new Map(sheet.needs.map(n => [n.id, n]))
  return sheet.pairs
    .filter(p => labels[p.pair_id] !== undefined)
    .map(p => {
      const n = needs.get(p.need_id)!
      return JSON.stringify({
        need: { id: n.id, role: n.role, grade: n.grade, skills: n.skills },
        candidate_id: p.candidate_id,
        candidate: { observed: p.observed },
        label: labels[p.pair_id],
      })
    })
    .join('\n')
}

/** «Специализация: X. Грейд: Y. …» → rows of a definition list. */
function cardLines(text: string) {
  return text.split(/\.\s+/).map(s => s.replace(/\.$/, '')).filter(Boolean).map(part => {
    const at = part.indexOf(': ')
    return at > 0 ? { term: part.slice(0, at), value: part.slice(at + 2) } : { term: null, value: part }
  })
}

function CardText({ text, testId }: { text: string; testId: string }) {
  return (
    <dl className="mt-2 space-y-1 text-sm" data-testid={testId}>
      {cardLines(text).map((line, i) => (
        <div key={i} className="flex flex-wrap gap-x-2">
          {line.term && <dt className="text-ink-3">{line.term}:</dt>}
          <dd className="text-ink">{line.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Summary({ report }: { report: EvaluateReport }) {
  const delta = report.paired_delta
  return (
    <section className="card mt-4 p-5" aria-labelledby="self-result" data-testid="self-result">
      <h2 id="self-result" className="font-display text-lg font-bold text-ink">Итог на ваших оценках</h2>
      <p className="mt-1 text-sm text-ink-2">
        {report.pairs} {plural(report.pairs, ['оценка', 'оценки', 'оценок'])} по {report.needs} {plural(report.needs, ['потребности', 'потребностям', 'потребностям'])}
        {report.judged_needs < report.needs ? `, в расчёт вошли ${report.judged_needs} — те, где есть кандидат на 2 или 3` : ''}.
        Каждый порядок переставляет только тех, кого вы оценили.
      </p>
      <table className="mt-3 w-full text-sm" data-testid="self-table">
        <thead>
          <tr className="text-left text-ink-3"><th className="py-1">Порядок</th><th>nDCG@10</th><th>P@5</th></tr>
        </thead>
        <tbody>
          {report.rows.map(row => (
            <tr key={row.method} className={`border-t border-line ${row.method === 'full' ? 'font-semibold' : ''}`}>
              <td className="py-1 text-ink">{METHOD_TITLE[row.method] ?? row.title}</td>
              <td className="num">{share(row.ndcg10)}</td>
              <td className="num">{share(row.p5)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-ink-3">
        nDCG@10 — насколько высоко стоят те, кому вы дали больше баллов (1 — идеальный порядок); P@5 — доля подходящих, с оценкой 2 или 3, среди первых пяти.
      </p>
      {delta && delta.mean !== null && (
        <p className="mt-3 text-sm text-ink-2" data-testid="self-delta">
          Модель минус «по резюме» по nDCG@10: <span className="num text-ink">{signed(delta.mean)}</span>
          {delta.needs > 1 ? ` (модель лучше в ${delta.model_better} из ${delta.needs}, хуже в ${delta.resume_better})` : ''}.
        </p>
      )}
      <p className="notice-info mt-3 text-sm" data-testid="self-caveat">
        Выборка маленькая: {report.pairs} {plural(report.pairs, ['оценка', 'оценки', 'оценок'])} одного человека.
        Пара других оценок может перевернуть итог, так что это проверка на глаз, а не вывод о качестве.
        Сводка по всем 200 парам листа, с минусами модели, — в docs/VALIDATION_MATCHING.md.
      </p>
    </section>
  )
}

/** «Разметить самому»: one blind card at a time, labels in localStorage, scores from POST /public/evaluate. */
export default function SelfLabel({ sheet }: { sheet: BlindSheet }) {
  const initial = useMemo(load, [])
  const [labels, setLabels] = useState<Labels>(initial.labels)
  const [needId, setNeedId] = useState<string | null>(
    initial.needId && sheet.needs.some(n => n.id === initial.needId) ? initial.needId : null)
  const [picked, setPicked] = useState(sheet.needs[0]?.id ?? '')
  const queue = useMemo(() => sheet.pairs.filter(p => p.need_id === needId), [sheet, needId])
  const firstOpen = (q: BlindPair[], l: Labels) => { const i = q.findIndex(p => l[p.pair_id] === undefined); return i < 0 ? q.length : i }
  const [cursor, setCursor] = useState(() => firstOpen(sheet.pairs.filter(p => p.need_id === needId), initial.labels))
  const run = useMutation({ mutationFn: (body: string) => evaluatePairs(body).then(r => r.data) })
  const needs = useMemo(() => new Map(sheet.needs.map(n => [n.id, n])), [sheet])
  const total = Object.keys(labels).length
  const done = needId !== null && cursor >= queue.length
  const pair = needId !== null && !done ? queue[cursor] : null
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => { save({ needId, labels }) }, [needId, labels])

  // The backend answers 422 when no need has a candidate rated 2 or 3; say so here instead of sending.
  const [noRelevant, setNoRelevant] = useState(false)
  const submit = useCallback((l: Labels) => {
    if (!Object.keys(l).length) return
    if (!hasRelevant(l)) { run.reset(); setNoRelevant(true); return }
    setNoRelevant(false)
    run.mutate(toJsonl(sheet, l))
  }, [run, sheet])

  const rate = useCallback((value: Label) => {
    if (!pair) return
    const next = { ...labels, [pair.pair_id]: value }
    setLabels(next)
    const after = cursor + 1
    setCursor(after)
    if (after >= queue.length) submit(next)
  }, [pair, labels, cursor, queue.length, submit])

  useEffect(() => {
    if (!pair) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const target = e.target as HTMLElement | null
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return
      if (e.key >= '0' && e.key <= '3') { e.preventDefault(); rate(Number(e.key) as Label) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pair, rate])

  useEffect(() => { if (run.data) resultRef.current?.scrollIntoView?.({ block: 'nearest' }) }, [run.data])

  const start = (id: string) => {
    setNeedId(id)
    setCursor(firstOpen(sheet.pairs.filter(p => p.need_id === id), labels))
  }
  const nextNeed = sheet.needs.find(n => n.id !== needId && sheet.pairs.some(p => p.need_id === n.id && labels[p.pair_id] === undefined))
  const reset = () => { setLabels({}); setNeedId(null); setCursor(0); run.reset() }
  const labelledIn = (id: string) => sheet.pairs.filter(p => p.need_id === id && labels[p.pair_id] !== undefined).length
  const sizeOf = (id: string) => sheet.pairs.filter(p => p.need_id === id).length

  return (
    <div>
      {needId === null ? (
        <form className="card space-y-3 p-5" onSubmit={e => { e.preventDefault(); if (picked) start(picked) }}>
          <p className="text-sm text-ink-2">
            Выберите потребность работодателя. Покажем восемь кандидатов по одному, в случайном порядке: трое из верха нашей модели,
            трое из верха сортировки по резюме и двое случайных. Чья это карточка и какой у неё балл, не видно.
            Оцените каждую от 0 до 3 — кнопкой или клавишей. Это займёт 2–3 минуты.
          </p>
          <label className="block text-sm text-ink-2" htmlFor="self-need">Потребность</label>
          <select id="self-need" className="input w-full" value={picked} onChange={e => setPicked(e.target.value)}>
            {sheet.needs.map(n => {
              const got = labelledIn(n.id)
              return <option key={n.id} value={n.id}>{n.text}{got ? ` — оценено ${got} из ${sizeOf(n.id)}` : ''}</option>
            })}
          </select>
          <div className="flex flex-wrap items-center gap-3">
            <button className="btn-primary" type="submit">Начать</button>
            {total > 0 && <button className="btn-secondary" type="button" onClick={() => submit(labels)} disabled={run.isPending}>Готово</button>}
            {total > 0 && <span className="text-sm text-ink-3">Уже оценено: {total}</span>}
          </div>
        </form>
      ) : (
        <section className="card p-5" aria-labelledby="self-need-title">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="self-need-title" className="font-display text-lg font-bold text-ink">Что ищет работодатель</h2>
            <span className="text-sm text-ink-3" data-testid="self-progress">
              Карточка {Math.min(cursor + 1, queue.length)} из {queue.length} · всего оценено {total}
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-label="Прогресс по потребности"
            aria-valuemin={0} aria-valuemax={queue.length} aria-valuenow={Math.min(cursor, queue.length)}>
            <div className="h-full bg-accent transition-all" style={{ width: `${(Math.min(cursor, queue.length) / Math.max(queue.length, 1)) * 100}%` }} />
          </div>
          <CardText text={needs.get(needId)?.text ?? ''} testId="self-need-card" />

          {pair ? (
            <>
              <div className="mt-4 rounded-lg border border-line bg-sunken/40 p-4">
                <h3 className="text-sm font-semibold text-ink">Кандидат</h3>
                <CardText text={pair.card} testId="self-candidate-card" />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="Ваша оценка">
                {SCALE.map(s => (
                  <button key={s.value} type="button" className="btn-secondary flex h-auto flex-col items-start gap-0.5 py-2 text-left"
                    aria-label={`Оценка ${s.value} — ${s.title.toLowerCase()}: ${s.hint}`} aria-keyshortcuts={String(s.value)}
                    onClick={() => rate(s.value)}>
                    <span className="num text-lg font-bold">{s.value}</span>
                    <span className="text-sm font-medium">{s.title}</span>
                    <span className="text-xs text-ink-3">{s.hint}</span>
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-ink-3">Клавиши 0–3 ставят оценку. Подтверждение навыка: тест сильнее резюме, резюме сильнее «заявлено».</p>
            </>
          ) : (
            <p className="notice-ok mt-4 text-sm">Все карточки этой потребности оценены. Итог ниже.</p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-primary" type="button" onClick={() => submit(labels)} disabled={run.isPending || total === 0}>Готово</button>
            {cursor > 0 && <button className="btn-ghost" type="button" onClick={() => setCursor(cursor - 1)}>Назад</button>}
            {done && nextNeed && <button className="btn-secondary" type="button" onClick={() => start(nextNeed.id)}>Ещё одна потребность</button>}
            <button className="btn-ghost" type="button" onClick={() => setNeedId(null)}>Сменить потребность</button>
            {total > 0 && <button className="btn-ghost" type="button" onClick={reset}>Стереть мои оценки</button>}
          </div>
          <p className="mt-2 text-xs text-ink-3">Оценки хранятся только в этом браузере. На сервер уходят лишь для расчёта и там не сохраняются.</p>
        </section>
      )}
      <div ref={resultRef}>
        {noRelevant && (
          <p className="notice-info mt-4 text-sm" role="status" data-testid="self-no-relevant">
            Посчитать пока нельзя: нужна хотя бы одна карточка с оценкой 2 или 3. Оцените ещё одну потребность или измените оценки.
          </p>
        )}
        {run.isPending && <p className="mt-4 text-sm text-ink-2" role="status">Считаем…</p>}
        {run.isError && (
          <p className="notice-error mt-4" role="alert">
            {apiError(run.error, 'Не удалось посчитать')}
          </p>
        )}
        {run.data && !run.isPending && <Summary report={run.data} />}
      </div>
    </div>
  )
}
