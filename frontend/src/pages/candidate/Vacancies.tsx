import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, applyToVacancy, vacanciesForMe } from '../../api/client'
import { roleRu } from '../../labels'

interface Card {
  id: string
  title: string
  company: string | null
  role: string | null
  grade: string | null
  work_format: string
  salary_from: number | null
  salary_to: number | null
  why: string[]
  matched_skills: string[]
  missing_skills: string[]
  applied: boolean
  can_apply: boolean
}

export default function CandidateVacancies() {
  const qc = useQueryClient()
  const { data: cards = [], isLoading } = useQuery({
    queryKey: ['vacanciesForMe'], queryFn: () => vacanciesForMe().then(r => r.data as Card[]),
  })
  const apply = useMutation({
    mutationFn: (id: string) => applyToVacancy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vacanciesForMe'] }),
  })
  if (isLoading) return <div className="animate-pulse h-64 bg-gray-100 rounded-2xl" />
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Вакансии под профиль</h1>
      <p className="text-sm text-text-muted">Отклик — это согласие показать контакты работодателю этой вакансии.</p>
      {cards.length === 0 && <p className="text-text-muted">Подходящих открытых вакансий нет.</p>}
      {apply.isError && <p className="text-sm text-fsp-red">{apiError(apply.error, 'Не удалось откликнуться')}</p>}
      {cards.map(card => (
        <article key={card.id} className="card space-y-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-semibold">{card.title}</h2>
              <p className="text-sm text-text-muted">{card.company} · {roleRu(card.role)} · {card.grade ?? 'грейд не задан'} · {card.work_format}</p>
            </div>
            <button disabled={card.applied || !card.can_apply || apply.isPending} onClick={() => apply.mutate(card.id)}
              className="btn-primary text-sm disabled:opacity-50">
              {card.applied ? 'Отклик отправлен' : card.can_apply ? 'Откликнуться' : 'Нужно согласие представителя'}
            </button>
          </div>
          {(card.salary_from || card.salary_to) && (
            <p className="text-sm">{card.salary_from?.toLocaleString('ru-RU')}–{card.salary_to?.toLocaleString('ru-RU')} ₽</p>
          )}
          <ul className="text-sm text-text-secondary">{card.why.map(line => <li key={line}>{line}</li>)}</ul>
        </article>
      ))}
    </div>
  )
}
