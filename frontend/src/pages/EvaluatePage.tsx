import { useState, type ChangeEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiError, evaluatePairs, type EvaluateNeedRow, type EvaluatePairedDelta } from '../api/client'
import PublicShell from '../components/PublicShell'
import { PageHeader, Skeleton } from '../components/ui'
import SelfLabel, { type BlindSheet } from './evaluate/SelfLabel'

const need = '{"id": "n1", "role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"]}'
const EXAMPLE = [
  `{"need": ${need}, "candidate_id": "c1", "candidate": {"observed": {"role": "backend", "grade": "middle", "grade_source": "assessed", "skills": {"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}, "test_p": 0.9, "fsp_lcb": 0.6, "industry": "fintech"}}, "label": 3}`,
  `{"need": ${need}, "candidate_id": "c2", "candidate": {"observed": {"role": "backend", "grade": "junior", "grade_source": "declared", "skills": {"Python": "self_reported"}, "test_p": null, "fsp_lcb": null, "industry": "fintech"}}, "label": 1}`,
  `{"need": ${need}, "candidate_id": "c3", "candidate": {"observed": {"role": "ml", "grade": "senior", "grade_source": "declared", "skills": {"Python": "self_reported"}, "test_p": null, "fsp_lcb": 0.4, "industry": "fintech"}}, "label": 0}`,
].join('\n')

const share = (v: number) => v.toFixed(3).replace('.', ',')
const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${share(Math.abs(v))}`

function DeltaLine({ delta }: { delta: EvaluatePairedDelta }) {
  if (delta.mean === null || !delta.ci) return <p className="mt-3 text-sm text-ink-2">Парной разницы нет: ни у одной потребности нет кандидата с оценкой 2 или 3.</p>
  return (
    <p className="mt-3 text-sm text-ink-2" data-testid="paired-delta">
      Модель минус «по резюме», nDCG@10 по потребностям: <span className="num text-ink">{signed(delta.mean)}</span>
      {' '}(95 % ДИ {signed(delta.ci[0])}…{signed(delta.ci[1])}, потребностей {delta.needs};
      модель лучше в {delta.model_better}, хуже в {delta.resume_better}).
    </p>
  )
}

function NeedTable({ rows }: { rows: EvaluateNeedRow[] }) {
  const worse = rows.filter(r => r.relevant > 0 && r.p_at_k_model < r.p_at_k_resume).length
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-sm font-medium text-ink">По потребностям ({rows.length}{worse ? `, модель хуже по P@k: ${worse}` : ''})</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm" data-testid="per-need-table">
          <thead>
            <tr className="text-left text-ink-3">
              <th className="py-1">Потребность</th><th>Пар / релев.</th><th>P@k модель</th><th>P@k по резюме</th>
              <th>nDCG@10 модель</th><th>nDCG@10 по резюме</th><th>Топ модели (оценка)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const lower = r.relevant > 0 && r.p_at_k_model < r.p_at_k_resume
              return (
                <tr key={r.need_id} className={`border-t border-line ${lower ? 'bg-warn-soft' : ''}`} data-lower={lower || undefined}>
                  <td className="py-1 text-ink">{r.need_id}{r.role ? <span className="text-ink-3"> · {r.role}{r.grade ? ` ${r.grade}` : ''}</span> : null}</td>
                  <td className="num">{r.judged} / {r.relevant}</td>
                  {r.relevant > 0 ? (
                    <>
                      <td className="num">{share(r.p_at_k_model)}</td>
                      <td className="num">{share(r.p_at_k_resume)}</td>
                      <td className="num">{share(r.ndcg10_model)}</td>
                      <td className="num">{share(r.ndcg10_resume)}</td>
                    </>
                  ) : <td colSpan={4} className="text-ink-3">нет кандидата с оценкой 2 или 3 — в средние не входит</td>}
                  <td className="font-mono text-xs text-ink-2">{r.top.map(t => `${t.candidate_id} (${t.label})`).join(', ')}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-ink-3">k = min(10, пар у потребности). Подсвечены строки, где доля релевантных в топе у модели ниже, чем у сортировки по резюме.</p>
    </details>
  )
}

/** Upload mode: the jury's own labelled pairs as JSONL. */
function UploadMode() {
  const [text, setText] = useState('')
  const run = useMutation({ mutationFn: (body: string) => evaluatePairs(body).then(r => r.data) })

  const open = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setText(await file.text())
  }

  return (
    <>
      <p className="mb-3 text-sm text-ink-2">
        Вставьте пары в JSONL: потребность, наблюдаемый профиль кандидата и ваша оценка 0–3. Страница посчитает nDCG@10,
        P@min(10, n) и MAP для модели, для сортировки по резюме и для случайного порядка.
      </p>
      <form className="card space-y-3 p-5" onSubmit={e => { e.preventDefault(); run.mutate(text) }}>
        <label className="block text-sm text-ink-2" htmlFor="pairs-jsonl">Пары, одна на строку (до 500, до 256 КБ)</label>
        <textarea id="pairs-jsonl" value={text} onChange={e => setText(e.target.value)} rows={10}
          className="input min-h-48 w-full font-mono text-xs" placeholder='{"need": {…}, "candidate": {"observed": {…}}, "label": 2}' />
        <div className="flex flex-wrap items-center gap-3">
          <button className="btn-primary" type="submit" disabled={run.isPending || !text.trim()}>Посчитать</button>
          <button className="btn-secondary" type="button" onClick={() => setText(EXAMPLE)}>Вставить пример</button>
          <label className="text-sm text-ink-2">
            <span className="sr-only">Файл JSONL</span>
            <input type="file" accept=".jsonl,.json,.txt" onChange={open} className="text-sm" />
          </label>
        </div>
      </form>
      {run.isError && <p className="notice-error mt-4" role="alert">{apiError(run.error, 'Не удалось посчитать')}</p>}
      {run.data && (
        <section className="card mt-4 p-5" aria-labelledby="evaluate-result">
          <h2 id="evaluate-result" className="font-display text-lg font-bold text-ink">Результат</h2>
          <p className="mt-1 text-sm text-ink-2">
            Пар {run.data.pairs}, потребностей {run.data.needs}, из них с оценкой 2 или 3 — {run.data.judged_needs}.
            Метрики считаются по ним.
          </p>
          <table className="mt-3 w-full text-sm" data-testid="evaluate-table">
            <thead>
              <tr className="text-left text-ink-3"><th className="py-1">Порядок</th><th>nDCG@10</th><th>P@10</th><th>MAP</th></tr>
            </thead>
            <tbody>
              {run.data.rows.map(row => (
                <tr key={row.method} className="border-t border-line">
                  <td className="py-1 text-ink">{row.title}</td>
                  <td className="num">
                    {share(row.ndcg10)}
                    {row.ndcg_ci && <span className="text-ink-3"> ({share(row.ndcg_ci[0])}–{share(row.ndcg_ci[1])})</span>}
                  </td>
                  <td className="num">{share(row.p10)}</td>
                  <td className="num">{share(row.map)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {run.data.paired_delta && <DeltaLine delta={run.data.paired_delta} />}
          {run.data.per_need && run.data.per_need.length > 0 && <NeedTable rows={run.data.per_need} />}
          <p className="mt-3 break-all font-mono text-xs text-ink-3">sha256 {run.data.sha256}</p>
        </section>
      )}
    </>
  )
}

const loadSheet = () => import('../data/blindSheet.json').then(m => m.default as unknown as BlindSheet)

function SelfMode() {
  const sheet = useQuery({ queryKey: ['blind-sheet-2029'], queryFn: loadSheet, staleTime: Infinity })
  if (sheet.isError) return <p className="notice-error" role="alert">Не удалось загрузить лист для разметки. Обновите страницу.</p>
  if (!sheet.data) return <Skeleton className="h-64" />
  return <SelfLabel sheet={sheet.data} />
}

type Mode = 'self' | 'upload'
const MODES: { id: Mode; title: string }[] = [{ id: 'self', title: 'Разметить самому' }, { id: 'upload', title: 'Загрузить JSONL' }]

/** The jury's own labels, scored by the model, the resume baseline and a random order. Nothing is stored on the server. */
export default function EvaluatePage() {
  const [mode, setMode] = useState<Mode>('self')
  return (
    <PublicShell>
      <PageHeader
        title="Проверка подбора на своей разметке"
        lead="Оцените кандидатов сами и сравните: насколько хорошо их упорядочила наша модель, сортировка по резюме и случайный порядок. Банк кандидатов не читается, ваши оценки на сервере не сохраняются."
      />
      <div className="mb-4 grid max-w-md grid-cols-2 rounded-lg bg-sunken p-1 text-sm" role="tablist" aria-label="Режим проверки">
        {MODES.map(m => (
          <button key={m.id} type="button" role="tab" id={`mode-${m.id}`} aria-selected={mode === m.id} aria-controls="mode-panel"
            onClick={() => setMode(m.id)}
            className={`flex min-h-9 items-center justify-center rounded-md text-center transition-colors ${mode === m.id ? 'bg-panel font-semibold text-ink shadow-xs ring-1 ring-line-strong' : 'text-ink-2 hover:text-ink'}`}>
            {m.title}
          </button>
        ))}
      </div>
      <div id="mode-panel" role="tabpanel" aria-labelledby={`mode-${mode}`}>
        {mode === 'self' ? <SelfMode /> : <UploadMode />}
      </div>
    </PublicShell>
  )
}
