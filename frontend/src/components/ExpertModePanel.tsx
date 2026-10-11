import { useState } from 'react'
import { apiError, simulateAssessment, type SimulatedRun } from '../api/client'
import { ROLE_RU, gradeRu } from '../labels'

const LEVELS = ['junior', 'middle', 'senior'] as const
const pct = (x: number) => `${Math.round(x * 100)} %`
const num = (x: number) => x.toFixed(2).replace('.', ',').replace('-', '−')

/** JS-02. The jury picks a level; the server runs the real test on a simulated candidate of that level. */
export default function ExpertModePanel() {
  const [spec, setSpec] = useState('backend')
  const [grade, setGrade] = useState<string>('middle')
  const [run, setRun] = useState<SimulatedRun | null>(null)
  const [previous, setPrevious] = useState<SimulatedRun | null>(null)
  const [batch, setBatch] = useState<SimulatedRun['batch'] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const start = async (repeat: boolean) => {
    setBusy(true)
    setError('')
    try {
      const response = await simulateAssessment({ spec, grade })
      setPrevious(repeat ? run : null)
      setRun(response.data)
      if (!repeat) setBatch(null)
    } catch (e) {
      setError(apiError(e, 'Прогон не выполнился'))
    } finally {
      setBusy(false)
    }
  }
  const runBatch = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await simulateAssessment({ spec, grade, batch: 50 })
      setBatch(response.data.batch ?? null)
    } catch (e) {
      setError(apiError(e, 'Пакет не выполнился'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card mt-8 space-y-3 p-5" aria-labelledby="expert-title">
      <h2 id="expert-title" className="font-display text-lg font-bold text-ink">Проверить тест за 2 минуты</h2>
      <p className="max-w-3xl text-sm text-ink-2">
        Выберите уровень — сервер проведёт настоящий адаптивный тест на виртуальном кандидате этого уровня:
        тот же выбор заданий, та же модель оценки и то же правило остановки, что у живого теста.
        Ответы кандидата моделируются, текст заданий и ключи не показываются, в базу ничего не пишется.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-ink-2">Специализация
          <select className="select mt-1" value={spec} onChange={e => setSpec(e.target.value)} aria-label="Специализация виртуального кандидата">
            {Object.entries(ROLE_RU).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
        <label className="text-sm text-ink-2">Настоящий уровень
          <select className="select mt-1" value={grade} onChange={e => setGrade(e.target.value)} aria-label="Уровень виртуального кандидата">
            {LEVELS.map(code => <option key={code} value={code}>{gradeRu(code)}</option>)}
          </select>
        </label>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => { void start(false) }}>Запустить тест</button>
        {run && <button type="button" className="btn-secondary" disabled={busy} onClick={() => { void start(true) }}>Повторить на новых заданиях</button>}
        {run && <button type="button" className="btn-secondary" disabled={busy} onClick={() => { void runBatch() }}>Ещё 50 прогонов</button>}
      </div>
      {error && <p className="notice-error" role="alert">{error}</p>}
      {run && (
        <div className="space-y-3" data-testid="expert-run">
          <p className="text-sm text-ink">
            Итог: {run.earned ? <>грейд <b>{gradeRu(run.earned)}</b></> : 'грейд не подтверждён'}
            {' '}за {run.items} из {run.max_items} заданий. Оценка уровня {num(run.theta_hat)} ± {num(run.se)},
            настоящий уровень кандидата {num(run.theta)} ({gradeRu(run.true_grade) || 'ниже стажёра'}).
            {run.stop_reason && <> Остановка: {run.stop_reason}.</>}
          </p>
          {previous && (
            <p className="text-sm text-ink" role="status">
              Повтор на новых заданиях: {previous.earned === run.earned ? 'грейд совпал' : 'грейд не совпал'}
              {' '}({gradeRu(previous.earned) || 'не подтверждён'} → {gradeRu(run.earned) || 'не подтверждён'}).
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Задания по шагам</caption>
              <thead className="text-ink-3">
                <tr>
                  <th scope="col">№</th>
                  <th scope="col">Семейство заданий</th>
                  <th scope="col"><abbr title="Уровень сложности задания от 1 до 5">Сложность</abbr></th>
                  <th scope="col">Ответ</th>
                  <th scope="col"><abbr title="Оценка уровня кандидата после этого ответа ± её погрешность (θ̂ ± SE)">Оценка ± погрешность</abbr></th>
                  <th scope="col"><abbr title="Вероятность, что уровень кандидата не ниже порога выбранного грейда">Шанс подтвердить</abbr></th>
                </tr>
              </thead>
              <tbody>
                {run.steps.map(step => (
                  <tr key={step.n} className="border-t border-line">
                    <td>{step.n}</td>
                    <td>{step.family}</td>
                    <td>{step.level}</td>
                    <td>{step.correct ? 'верно' : 'неверно'}</td>
                    <td className="font-mono">{num(step.theta)} ± {num(step.se)}</td>
                    <td>{pct(step.p_pass)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {batch && (
        <p className="text-sm text-ink" data-testid="expert-batch">
          {batch.n} прогонов на новых заданиях: тот же грейд, что в первом, — {pct(batch.same_as_first)};
          {' '}совпал с настоящим уровнем — {pct(batch.same_as_truth)}; медиана {batch.median_items} заданий.
        </p>
      )}
    </section>
  )
}
