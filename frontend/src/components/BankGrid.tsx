import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { searchBank } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'

interface Cell { role: string; grade: string; hidden: boolean; candidates: number | null; tested: number | null }

/** The bank as a showcase: specialization × grade, people and how many confirmed the grade by test.
 * A cell opens the search with these filters. Cells under five people are hidden. */
export default function BankGrid() {
  const { data, isLoading } = useQuery({ queryKey: ['searchBank'], queryFn: () => searchBank().then(r => r.data as { min_cell: number; cells: Cell[] }) })
  if (isLoading || !data) return null
  const at = (role: string, grade: string) => data.cells.find(c => c.role === role && c.grade === grade)
  const roles = Object.keys(ROLE_RU).filter(r => data.cells.some(c => c.role === r))
  return (
    <section aria-labelledby="bank-title" className="card mt-4">
      <h2 id="bank-title" className="section-title">Банк кандидатов</h2>
      <p className="mt-1 text-sm text-ink-2">Сколько людей в поиске по специализации и грейду, в скобках — из них грейд подтверждён тестом. Ячейка открывает поиск с этими фильтрами. Меньше {data.min_cell} человек не показываем.</p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[34rem] border-collapse text-sm">
          <thead>
            <tr>
              <th scope="col" className="py-2 pr-3 text-left font-medium text-ink-2">Специализация</th>
              {GRADES.map(g => <th key={g} scope="col" className="px-2 py-2 text-left font-medium text-ink-2">{gradeRu(g)}</th>)}
            </tr>
          </thead>
          <tbody>
            {roles.map(role => (
              <tr key={role} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal text-ink">{ROLE_RU[role]}</th>
                {GRADES.map(grade => {
                  const c = at(role, grade)
                  return (
                    <td key={grade} className="px-1 py-1">
                      {!c ? <span className="px-2 text-ink-3">—</span>
                        : c.hidden ? <span className="px-2 text-ink-3" title={`Меньше ${data.min_cell} человек`}>&lt; {data.min_cell}</span>
                          : (
                            <Link to={`/employer/search?role=${role}&grade=${grade}`} className="num inline-flex min-h-6 items-center rounded-md px-2 py-1 text-accent hover:bg-sunken"
                              aria-label={`${ROLE_RU[role]}, ${gradeRu(grade)}: ${c.candidates} в поиске, ${c.tested} с тестом`}>
                              {c.candidates}<span className="ml-1 text-ink-3">({c.tested})</span>
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
