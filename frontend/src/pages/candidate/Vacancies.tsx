import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, answerPractice, applyToVacancy, myApplications, startPractice, vacanciesForMe } from '../../api/client'
import { CategoryPlate, Empty, PageHeader, Skeleton, rub } from '../../components/ui'

interface Card {
  id: string; title: string; company: string | null; role: string | null; grade: string | null; work_format: string
  salary_from: number | null; salary_to: number | null; why: string[]; matched_skills: string[]; missing_skills: string[]
  applied: boolean; can_apply: boolean
}
const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }

interface PracticeItem {
  id: string; stem: string; code: string | null; options: { index: number; text: string }[]
  topic_label: string; is_correct?: boolean; explanation?: string; answered?: boolean
}
interface Mine { id: string; title: string; status: string }

export default function CandidateVacancies() {
  const qc = useQueryClient()
  const [task, setTask] = useState<PracticeItem | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [taskError, setTaskError] = useState('')
  const [params] = useSearchParams()
  const topic = params.get('topic')
  const { data: cards = [], isLoading } = useQuery({ queryKey: ['vacanciesForMe'], queryFn: () => vacanciesForMe().then(r => r.data as Card[]) })
  const { data: mine = [] } = useQuery({ queryKey: ['myApplications'], queryFn: () => myApplications().then(r => r.data as Mine[]) })
  const practice = useMutation({
    mutationFn: (opts: { vacancy_id?: string; topic?: string }) => startPractice(opts).then(r => r.data as PracticeItem),
    onSuccess: item => { setTaskError(''); setPicked(null); setTask(item) },
    onError: (e: unknown) => setTaskError(apiError(e, 'Задание не собрано')),
  })
  useEffect(() => { if (topic) practice.mutate({ topic }) }, [topic])
  const submitPractice = useMutation({
    mutationFn: () => answerPractice(task!.id, picked!).then(r => r.data as PracticeItem),
    onSuccess: item => setTask(item),
    onError: (e: unknown) => setTaskError(apiError(e, 'Ответ не принят')),
  })
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
      {taskError && <p className="notice-error mb-4" role="alert">{taskError}</p>}
      {task && (
        <section className="card mb-6">
          <p className="text-xs text-ink-3">{task.topic_label}. Одно задание, грейд не меняется.</p>
          <p className="mt-2 text-ink">{task.stem}</p>
          {task.code && <pre className="mt-3 overflow-x-auto rounded bg-sunken p-3 text-sm">{task.code}</pre>}
          <ul className="mt-3 space-y-2">
            {task.options.map(o => (
              <li key={o.index}>
                <button type="button" className={picked === o.index ? 'chip-active' : 'chip-default'}
                  disabled={task.answered} onClick={() => setPicked(o.index)}>{o.text}</button>
              </li>
            ))}
          </ul>
          {task.answered ? (
            <p className="mt-3 text-sm text-ink">{task.is_correct ? 'Верно.' : 'Неверно.'} {task.explanation}</p>
          ) : (
            <button type="button" className="btn-primary mt-4" disabled={picked == null || submitPractice.isPending}
              onClick={() => submitPractice.mutate()}>Ответить</button>
          )}
        </section>
      )}
      {mine.length > 0 && (
        <section className="mb-6">
          <h2 className="section-title">Мои отклики</h2>
          <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-panel">
            {mine.map(a => <li key={a.id} className="flex justify-between px-4 py-2 text-sm"><span>{a.title}</span><span className="text-ink-3">{({ applied: 'отправлен', reviewing: 'смотрят', invited: 'приглашение', rejected: 'отказ', closed: 'закрыт' } as Record<string, string>)[a.status] ?? a.status}</span></li>)}
          </ul>
        </section>
      )}
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
                {(card.salary_from || card.salary_to) && <p className="num font-display text-lg font-bold text-ink">{rub(card.salary_from)} – {rub(card.salary_to)}</p>}
                <Link to={`/candidate/assessment?vacancy=${card.id}`} className="btn-ghost mt-3 block text-sm">Тест по этой вакансии</Link>
                <button type="button" className="btn-ghost mt-1 block text-sm" onClick={() => practice.mutate({ vacancy_id: card.id })}>Короткая практика</button>
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
