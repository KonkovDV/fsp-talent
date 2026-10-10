import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiError, itemPsychometrics, methodWeights, previewPublicExam } from '../api/client'
import ExamPreview, { type Exam } from '../components/ExamPreview'
import PublicShell from '../components/PublicShell'
import { PageHeader, Skeleton } from '../components/ui'
import { GRADE_RU, ROLE_RU } from '../labels'
import { FIGURES, SIMULATION_KEY_SHARE, shareLabel } from '../methodFigures'

interface Cut { grade: string; cut: number; information: number; se_after_12: number | null }
interface Point { theta: number; information: number }
interface FamilyRow { family_id: string; title: string; answers: number; cusum: number; quarantined: number; max_share: number }
interface ParentLevel { level: number; b: number }
interface ParentRow { family_id: string; title: string; a: number; levels: ParentLevel[] }
interface Report {
  spec: string; randomesque: number; answers: number; max_share: number; exposure_target: number
  cuts: Cut[]; curve: Point[]; families: FamilyRow[]; parents: ParentRow[]
}

function InfoCurve({ curve, cuts }: { curve: Point[]; cuts: Cut[] }) {
  const w = 640
  const h = 180
  const padX = 16
  const padY = 12
  const peak = Math.max(0.001, ...curve.map(p => p.information))
  const x = (theta: number) => padX + ((theta + 3) / 6) * (w - padX * 2)
  const y = (info: number) => h - padY - (info / peak) * (h - padY * 2)
  const d = curve.map((p, i) => `${i ? 'L' : 'M'}${x(p.theta).toFixed(1)},${y(p.information).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 h-44 w-full" role="img"
      aria-label={`Кривая информации от −3 до 3, максимум ${peak.toFixed(2)}. Вертикальные линии — пороги грейдов.`}>
      <line x1={padX} x2={w - padX} y1={h - padY} y2={h - padY} stroke="rgb(var(--ink-3))" strokeWidth="1" />
      {cuts.map(cut => (
        <line key={cut.grade} x1={x(cut.cut)} x2={x(cut.cut)} y1={padY} y2={h - padY}
          stroke="rgb(var(--ink-3))" strokeDasharray="3 3" />
      ))}
      <path d={d} fill="none" stroke="rgb(var(--accent))" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>
  )
}

function ExposureBars({ families, answers, target }: { families: FamilyRow[]; answers: number; target: number }) {
  const w = 640
  const h = 176
  const padX = 16
  const padY = 12
  const rows = families
    .filter(row => row.answers > 0)
    .sort((a, b) => b.answers - a.answers || a.family_id.localeCompare(b.family_id))
  if (answers === 0 || rows.length === 0) {
    return (
      <>
        <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 h-36 w-full" role="img" aria-label="Показов ещё нет">
          <line x1={padX} x2={w - padX} y1={h / 2} y2={h / 2} stroke="rgb(var(--ink-3))" strokeWidth="1.5" />
          <text x={w / 2} y={h / 2 - 12} textAnchor="middle" fill="rgb(var(--ink-2))" fontSize="14">Показов ещё нет</text>
        </svg>
        <p className="mt-2 text-sm text-ink-2">
          На этом стенде ответы ещё не копились. В симуляции 2000 кандидатов максимальная доля одного ключа — {SIMULATION_KEY_SHARE}.
        </p>
      </>
    )
  }
  const shares = rows.map(row => row.answers / answers)
  const ceiling = Math.max(target, ...shares)
  const plotTop = padY + 18
  const plotBottom = h - padY
  const yOf = (share: number) => plotBottom - (share / ceiling) * (plotBottom - plotTop)
  const gap = 6
  const barW = (w - padX * 2 - gap * (rows.length - 1)) / rows.length
  const top = shareLabel(shares[0])
  return (
    <>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 h-44 w-full" role="img"
        aria-label={`Показы по семействам, максимум ${top}`}>
        <line x1={padX} x2={w - padX} y1={plotBottom} y2={plotBottom} stroke="rgb(var(--ink-3))" strokeWidth="1" />
        <line x1={padX} x2={w - padX} y1={yOf(target)} y2={yOf(target)}
          stroke="rgb(var(--ink-2))" strokeWidth="1.5" strokeDasharray="4 4" />
        {rows.map((row, i) => {
          const x = padX + i * (barW + gap)
          const y = yOf(shares[i])
          return (
            <g key={row.family_id}>
              <rect data-family={row.family_id} data-answers={row.answers} x={x} y={y} width={barW} height={plotBottom - y}
                fill="rgb(var(--accent))" rx="2" />
              {i < 3 && (
                <text x={x + barW / 2} y={y - 4} textAnchor="middle" fill="rgb(var(--ink))" fontSize="12">
                  {shareLabel(shares[i])}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      <p className="mt-2 text-sm font-medium text-ink">
        {rows.slice(0, 3).map(row => shareLabel(row.answers / answers)).join(' · ')}
      </p>
      <p className="mt-1 text-sm text-ink-2">
        Максимальная доля показов одного семейства: {top} на стенде; в симуляции 2000 кандидатов — {SIMULATION_KEY_SHARE}.
        Доля по всем специализациям. Внутри специализации до 69 % — предел глубины банка; калибровка Симпсона–Хеттера не прошла отложенные зёрна.
        Числа в задании каждый раз другие, поэтому частое семейство не выдаёт ответ.
        Пунктир — целевая доля одного ключа {target.toFixed(2).replace('.', ',')}.
      </p>
    </>
  )
}

/** Open view of the item bank: information at the cuts, exposure, no answer keys. */
export default function MethodPage() {
  const [spec, setSpec] = useState('backend')
  const [vacancy, setVacancy] = useState('Ищем backend-разработчика на Python и PostgreSQL')
  const demo = useMutation({
    mutationFn: () => previewPublicExam({ description: vacancy, role: spec, grade: 'middle' }).then(r => r.data as Exam),
  })
  const weights = useQuery({
    queryKey: ['methodWeights'],
    queryFn: () => methodWeights().then(r => r.data),
    retry: false,
  })
  const { data, isLoading, isError } = useQuery<Report>({
    queryKey: ['psychometrics', spec],
    queryFn: () => itemPsychometrics(spec).then(r => r.data),
  })
  return (
    <PublicShell>
      <PageHeader
        title="Как устроен тест"
        lead="Задание выбирается там, где оно лучше всего отделяет заявленный уровень от соседнего. Среди пяти лучших срабатывает Симпсон–Хеттер: без измеренной экспозиции выбор равномерный, а ключ чаще целевой доли берётся реже. Здесь параметры и счётчики показов, без текстов и правильных ответов."
        actions={
          <select value={spec} onChange={e => setSpec(e.target.value)} className="select w-auto" aria-label="Специализация">
            {Object.entries(ROLE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        }
      />
      {weights.data && (
        <section className="card mb-6 p-5">
          <h2 className="font-display text-lg font-bold text-ink">Веса балла на этом стенде</h2>
          <p className="mt-1 text-sm text-ink-2">{weights.data.note} Вне демо этот блок скрыт. Грейд этими весами не ставится.</p>
          <ul className="mt-3 text-sm text-ink">
            {weights.data.fit.map(item => <li key={item.key}>{item.label}: {item.weight}</li>)}
          </ul>
          <p className="mt-2 text-sm text-ink-2">Рядом с соответствием свидетельство с весом {weights.data.evidence_weight}: {weights.data.evidence.map(item => `${item.label} ${item.weight}`).join(', ')}.</p>
        </section>
      )}
      {isLoading && <Skeleton className="h-64" />}
      {isError && <p className="text-sm text-ink-2">Сводка банка сейчас недоступна.</p>}
      {data && (
        <div className="space-y-6">
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Цифры проверки</h2>
            <p className="mt-1 text-sm text-ink-2">Каждая цифра печатается своей командой из каталога репозитория. Это тот же прогон, что в README.</p>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {FIGURES.map(([value, text, command]) => (
                <li key={value} className="rounded-lg border border-line bg-sunken/40 p-3">
                  <p className="font-display text-2xl font-bold text-accent">{value}</p>
                  <p className="mt-1 text-sm text-ink">{text}</p>
                  <p className="mt-2 break-all font-mono text-xs text-ink-3">{command}</p>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-ink-2">
              Согласованность без порога 0,75 — 79 %. По правилу «сдавать от 75 %» модель предсказывает 76,1 %,
              повтор даёт 73,6 %. Обе цифры печатает команда каппы.
            </p>
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Какой тест получится из вакансии</h2>
            <p className="mt-1 text-sm text-ink-2">Вставьте описание. Вход не нужен. Правильные ответы не показываются.</p>
            <textarea value={vacancy} onChange={e => setVacancy(e.target.value)} rows={4} className="input mt-3" aria-label="Текст вакансии" />
            <button type="button" className="btn-primary mt-3" disabled={vacancy.trim().length < 2 || demo.isPending} onClick={() => demo.mutate()}>
              {demo.isPending ? 'Считаем…' : 'Показать состав'}
            </button>
            {demo.isError && <p className="notice-error mt-3" role="alert">{apiError(demo.error)}</p>}
            {demo.data && <div className="mt-4"><ExamPreview exam={demo.data} /></div>}
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Информация у порога уровня</h2>
            <p className="mt-1 text-sm text-ink-2">
              Симпсон–Хеттер среди {data.randomesque} лучших заданий: без измеренной экспозиции выбор равномерный. Погрешность в строке — если двенадцать заданий
              несут информацию лучшего у этого порога.
              {data.cuts.every(c => c.information === data.cuts[0].information) && ' У каждого порога рядом стоит уровень семейства, поэтому информация лучшего задания совпадает. Кривая ниже показывает, как она меняется между порогами.'}
            </p>
            <ul className="mt-4 divide-y divide-line">
              {data.cuts.map(cut => (
                <li key={cut.grade} className="flex flex-col gap-0.5 py-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                  <span className="font-medium text-ink">{GRADE_RU[cut.grade] ?? cut.grade}</span>
                  <span className="num text-sm text-ink-2">
                    порог {cut.cut.toFixed(1)} · информация {cut.information.toFixed(3)} · погрешность {cut.se_after_12 == null ? '—' : cut.se_after_12.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Родители семейств</h2>
            <p className="mt-1 text-sm text-ink-2">
              Каждый показ — новый изоморф: другие числа и код. В оценке у всех изоморфов одного уровня
              общие параметры родителя. Различимость a — априор семейства, по ответам она в банк не пишется.
              Трудность b задаёт уровень.
            </p>
            <ul className="mt-4 divide-y divide-line">
              {data.parents.map(row => {
                const first = row.levels[0]
                const last = row.levels[row.levels.length - 1]
                return (
                  <li key={row.family_id} className="flex flex-col gap-0.5 py-2 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                    <span className="font-medium text-ink">{row.title}</span>
                    <span className="num text-sm text-ink-2">
                      a {row.a.toFixed(1)} · b {first.b.toFixed(1)} … {last.b.toFixed(1)}
                    </span>
                  </li>
                )
              })}
            </ul>
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Кривая информации</h2>
            <p className="mt-1 text-sm text-ink-2">Лучшее задание специализации на каждом участке шкалы θ. Пунктир — порог грейда.</p>
            <InfoCurve curve={data.curve} cuts={data.cuts} />
            <p className="mt-2 text-xs text-ink-3">41 точка, от θ = −3 до θ = 3, шаг 0,15.</p>
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Справедливость показа</h2>
            <p className="mt-1 text-sm text-ink-2">
              В оценке нет пола, возраста и региона. Правило четырёх пятых на синтетике парное: отношение ровно 1.
              На симуляции 2 000 кандидатов, зерно 7, метки регионов в выбор задания не входят. Максимальная доля
              одного ключа в четырёх группах: 33 %, 35 %, 33 % и 37 %. Отношение меньшей к большей — 0,88.
            </p>
          </section>
          <section className="card p-5">
            <h2 className="font-display text-lg font-bold text-ink">Показы по семействам</h2>
            <ExposureBars families={data.families} answers={data.answers} target={data.exposure_target} />
            {data.answers > 0 && (
              <>
                <p className="mt-1 text-xs text-ink-3">
                  Всего ответов {data.answers}. Сумма CUSUM — накопленный избыток верных ответов над моделью. Карантин решается по каждому ключу.
                </p>
                <ul className="mt-4 divide-y divide-line sm:hidden">
                  {data.families.filter(f => f.answers > 0).map(f => (
                    <li key={f.family_id} className="py-2">
                      <p className="font-medium text-ink">{f.title}</p>
                      <p className="num text-sm text-ink-2">
                        Ответы {f.answers}. Доля самого частого {shareLabel(f.max_share)}. Сумма CUSUM {f.cusum.toFixed(2)}. В карантине {f.quarantined}.
                      </p>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 hidden w-0 min-w-full overflow-x-auto rounded-lg sm:block" tabIndex={0} role="region" aria-label="Таблица показов по семействам">
                  <table className="protocol">
                    <thead>
                      <tr>
                        <th>Семейство</th>
                        <th className="text-right">Ответы</th>
                        <th className="text-right">Доля самого частого</th>
                        <th className="text-right">Сумма CUSUM</th>
                        <th className="text-right">В карантине</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.families.filter(f => f.answers > 0).map(f => (
                        <tr key={f.family_id}>
                          <td>{f.title}</td>
                          <td className="text-right num">{f.answers}</td>
                          <td className="text-right num">{shareLabel(f.max_share)}</td>
                          <td className="text-right num">{f.cusum.toFixed(2)}</td>
                          <td className="text-right num">{f.quarantined}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </PublicShell>
  )
}
