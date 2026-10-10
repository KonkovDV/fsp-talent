import { useState, type ChangeEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { apiError, evaluatePairs } from '../api/client'
import PublicShell from '../components/PublicShell'
import { PageHeader } from '../components/ui'

const need = '{"id": "n1", "role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"]}'
const EXAMPLE = [
  `{"need": ${need}, "candidate_id": "c1", "candidate": {"observed": {"role": "backend", "grade": "middle", "grade_source": "assessed", "skills": {"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}, "test_p": 0.9, "fsp_lcb": 0.6, "industry": "fintech"}}, "label": 3}`,
  `{"need": ${need}, "candidate_id": "c2", "candidate": {"observed": {"role": "backend", "grade": "junior", "grade_source": "declared", "skills": {"Python": "self_reported"}, "test_p": null, "fsp_lcb": null, "industry": "fintech"}}, "label": 1}`,
  `{"need": ${need}, "candidate_id": "c3", "candidate": {"observed": {"role": "ml", "grade": "senior", "grade_source": "declared", "skills": {"Python": "self_reported"}, "test_p": null, "fsp_lcb": 0.4, "industry": "fintech"}}, "label": 0}`,
].join('\n')

const share = (v: number) => v.toFixed(3).replace('.', ',')

/** The jury's own labelled pairs, scored by the model and by the resume baseline. Nothing is stored. */
export default function EvaluatePage() {
  const [text, setText] = useState('')
  const run = useMutation({ mutationFn: (body: string) => evaluatePairs(body).then(r => r.data) })

  const open = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setText(await file.text())
  }

  return (
    <PublicShell>
      <PageHeader
        title="Проверка подбора на своей разметке"
        lead="Вставьте пары в JSONL: потребность, наблюдаемый профиль кандидата и ваша оценка 0–3. Страница посчитает nDCG@10, P@min(10, n) и MAP для модели, для сортировки по резюме и для случайного порядка. Пары не сохраняются, банк кандидатов не читается."
      />
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
          <p className="mt-3 break-all font-mono text-xs text-ink-3">sha256 {run.data.sha256}</p>
        </section>
      )}
    </PublicShell>
  )
}
