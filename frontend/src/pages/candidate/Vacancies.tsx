import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, applyToVacancy, vacanciesForMe } from '../../api/client'
import { CategoryPlate, Empty, PageHeader, Skeleton, rub } from '../../components/ui'

interface Card {
  id: string; title: string; company: string | null; role: string | null; grade: string | null; work_format: string
  salary_from: number | null; salary_to: number | null; why: string[]; matched_skills: string[]; missing_skills: string[]
  applied: boolean; can_apply: boolean
}
const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }

export default function CandidateVacancies() {
  const qc = useQueryClient()
  const { data: cards = [], isLoading } = useQuery({ queryKey: ['vacanciesForMe'], queryFn: () => vacanciesForMe().then(r => r.data as Card[]) })
  const apply = useMutation({
    mutationFn: (id: string) => applyToVacancy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vacanciesForMe'] }),
  })
  return (
    <div>
      <PageHeader title="Вакансии под профиль"
        lead="Второй путь, кроме приглашений: откликнуться самому. Отклик — согласие показать контакты работодателю этой вакансии." />
      {isLoading && <Skeleton className="h-48" />}
      {!isLoading && cards.length === 0 && <Empty title="Подходящих открытых вакансий нет">Они появятся, когда работодатели опубликуют вакансии вашей специализации.</Empty>}
      {apply.isError && <p className="notice-error mb-4" role="alert">{apiError(apply.error, 'Не удалось откликнуться')}</p>}
      <ul className="space-y-4">
        {cards.map(card => (
          <li key={card.id} className="card">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm text-ink-2">{card.company}</p>
                <h2 className="mt-0.5 text-lg font-semibold text-ink">{card.title}</h2>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
                  <CategoryPlate role={card.role} grade={card.grade} /> {FORMAT[card.work_format] ?? card.work_format}
                </div>
              </div>
              <div className="text-right">
                {(card.salary_from || card.salary_to) && <p className="num font-display text-lg font-semibold text-ink">{rub(card.salary_from)} – {rub(card.salary_to)}</p>}
                <button disabled={card.applied || !card.can_apply || apply.isPending} onClick={() => apply.mutate(card.id)}
                  className={card.applied ? 'btn-secondary mt-3' : 'btn-primary mt-3'}>
                  {card.applied ? 'Отклик отправлен' : card.can_apply ? 'Откликнуться' : 'Нужно согласие представителя'}
                </button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {card.matched_skills.map(s => <span key={s} className="chip-active">{s}</span>)}
              {card.missing_skills.map(s => <span key={s} className="chip-missing">нет {s}</span>)}
            </div>
            {card.why.length > 0 && <ul className="mt-3 space-y-0.5 text-sm text-ink-2">{card.why.map(l => <li key={l}>{l}</li>)}</ul>}
          </li>
        ))}
      </ul>
    </div>
  )
}
