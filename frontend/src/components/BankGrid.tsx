import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { searchBank } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'

interface Cell { role: string; grade: string; hidden: boolean; candidates: number | null; tested: number | null }

/** The bank as a showcase: specialization × grade, people and how many confirmed the grade by test.
 * A cell opens the search with these filters. Cells under five people are hidden. */
export default function BankGrid() {
  const { data, isLoading, isError } = useQuery({ queryKey: ['searchBank'], queryFn: () => searchBank().then(r => r.data as { min_cell: number; cells: Cell[] }) })
  if (isLoading) return null
  if (isError || !data) return <p className="mt-3 text-sm text-ink-2">Банк сейчас не загрузился.</p>
  const at = (role: string, grade: string) => data.cells.find(c => c.role === role && c.grade === grade)
  const roles = Object.keys(ROLE_RU).filter(r => data.cells.some(c => c.role === r))
  const max = Math.max(1, ...data.cells.map(c => (c.hidden ? 0 : c.candidates ?? 0)))
  // Four steps of the accent; the darkest carries accent-ink text, the rest ink: both ≥ 4.5:1 in either theme.
  const tone = (n: number) => { const r = n / max; return r > 0.75 ? 0.85 : r > 0.45 ? 0.45 : r > 0.2 ? 0.25 : 0.1 }
  return (
    <section aria-labelledby="bank-title" className="card mt-4">
      <div className="card-head">
        <h2 id="bank-title" className="section-title">Банк кандидатов</h2>
        <p className="flex items-center gap-1.5 text-2xs text-ink-3" aria-hidden>
          меньше<span className="flex gap-0.5">{[0.1, 0.25, 0.45, 0.85].map(a => <span key={a} className="h-3 w-4 rounded-sm" style={{ background: `rgb(var(--accent) / ${a})` }} />)}</span>больше
        </p>
      </div>
      <p className="mt-1 max-w-[72ch] text-sm text-ink-2">Сколько людей в поиске по специализации и грейду, в скобках — из них грейд подтверждён тестом. Число — по основной категории; в поиске добавятся те, кто подтвердил эту пару второй специализацией. Ячейка открывает поиск с этими фильтрами. Меньше {data.min_cell} человек не показываем.</p>
      <div className="mt-4 overflow-x-auto" tabIndex={0} role="region" aria-label="Банк кандидатов по специализациям и грейдам">
        <table className="w-full min-w-[36rem] table-fixed border-separate border-spacing-1 text-sm">
          <thead>
            <tr>
              <th scope="col" className="w-[30%] pb-1 pr-3 text-left text-xs font-medium text-ink-3">Специализация</th>
              {GRADES.map(g => <th key={g} scope="col" className="pb-1 text-center text-xs font-medium text-ink-3">{gradeRu(g)}</th>)}
            </tr>
          </thead>
          <tbody>
            {roles.map(role => (
              <tr key={role}>
                <th scope="row" className="truncate pr-3 text-left font-medium text-ink">{ROLE_RU[role]}</th>
                {GRADES.map(grade => {
                  const c = at(role, grade)
                  const a = c && !c.hidden ? tone(c.candidates ?? 0) : 0
                  return (
                    <td key={grade} className="h-11 p-0">
                      {!c ? <span className="flex h-full items-center justify-center rounded-md bg-sunken text-ink-3">—</span>
                        : c.hidden ? <span className="flex h-full items-center justify-center rounded-md bg-sunken text-xs text-ink-3" title={`Меньше ${data.min_cell} человек`}>&lt; {data.min_cell}</span>
                          : (
                            <Link to={`/employer/search?role=${role}&grade=${grade}`}
                              className={`num flex h-full items-center justify-center gap-1 rounded-md font-display font-bold outline-offset-1 transition-[box-shadow] hover:ring-2 hover:ring-accent ${a > 0.8 ? 'text-accent-ink' : 'text-ink'}`}
                              style={{ background: `rgb(var(--accent) / ${a})` }}
                              aria-label={`${ROLE_RU[role]}, ${gradeRu(grade)}: ${c.candidates} в поиске, ${c.tested} с тестом`}>
                              {c.candidates}<span className="font-sans text-xs font-normal">({c.tested})</span>
                            </Link>
                          )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
