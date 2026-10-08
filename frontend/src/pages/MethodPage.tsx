import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { itemPsychometrics } from '../api/client'
import PublicShell from '../components/PublicShell'
import { PageHeader, Skeleton } from '../components/ui'
import { GRADE_RU, ROLE_RU } from '../labels'

interface Cut { grade: string; cut: number; information: number; se_after_12: number | null }
interface Point { theta: number; information: number }
interface FamilyRow { family_id: string; title: string; answers: number; cusum: number; quarantined: number; max_share: number }
interface ParentLevel { level: number; b: number }
interface ParentRow { family_id: string; title: string; a: number; levels: ParentLevel[] }
interface Report {
  spec: string; randomesque: number; answers: number; max_share: number
  cuts: Cut[]; curve: Point[]; families: FamilyRow[]; parents: ParentRow[]
}

const FIGURES: [string, string, string][] = [
  ['91,5 %', 'верных решений вдали от границы грейда, 2000 кандидатов', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,47', 'каппа Коэна повторного теста с новыми заданиями', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,22', 'медиана r, различающая сила вводимого ответа', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0 %', 'случайное угадывание проходит тест', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['65,1 %', 'точный итоговый грейд после пути по правилам продукта; в пределах ступени 98,6 %', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
]

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

function ExposureCurve({ families, answers }: { families: FamilyRow[]; answers: number }) {
  const w = 640
  const h = 160
  const padX = 16
  const padY = 16
  const rows = families.filter(f => f.answers > 0)
  if (answers === 0 || rows.length === 0) {
    return (
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 h-36 w-full" role="img" aria-label="Показов ещё нет">
        <line x1={padX} x2={w - padX} y1={h / 2} y2={h / 2} stroke="rgb(var(--ink-3))" strokeWidth="1.5" />
        <text x={w / 2} y={h / 2 - 12} textAnchor="middle" fill="rgb(var(--ink-2))" fontSize="14">Показов ещё нет</text>
      </svg>
    )
  }
  const peak = Math.max(...rows.map(row => row.answers))
  const x = (i: number) => padX + (rows.length === 1 ? 0 : (i / (rows.length - 1)) * (w - padX * 2))
  const y = (n: number) => h - padY - (n / peak) * (h - padY * 2)
  const d = rows.map((row, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(row.answers).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 h-40 w-full" role="img"
      aria-label={`Доля показов по ${rows.length} семействам, всего ответов ${answers}`}>
      <line x1={padX} x2={w - padX} y1={h - padY} y2={h - padY} stroke="rgb(var(--ink-3))" strokeWidth="1" />
      <path d={d} fill="none" stroke="rgb(var(--accent))" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>
  )
}

/** Open view of the item bank: information at the cuts, exposure, no answer keys. */
export default function MethodPage() {
  const [spec, setSpec] = useState('backend')
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
            <ExposureCurve families={data.families} answers={data.answers} />
            {data.answers === 0 ? (
              <p className="mt-2 text-sm text-ink-2">На этом стенде ответы ещё не копились. Максимальная доля одного задания на симуляции опубликована в отчёте проверки теста.</p>
            ) : (
              <>
                <p className="mt-1 text-sm text-ink-2">
                  Всего ответов {data.answers}. Самое частое задание — {Math.round(data.max_share * 1000) / 10} % показов.
                  Сумма CUSUM — накопленный избыток верных ответов над моделью; карантин по-прежнему решается по каждому ключу.
                </p>
                <div className="mt-4 overflow-x-auto rounded-lg" tabIndex={0} role="region" aria-label="Таблица показов по семействам">
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
                          <td className="text-right num">{Math.round(f.max_share * 1000) / 10} %</td>
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
