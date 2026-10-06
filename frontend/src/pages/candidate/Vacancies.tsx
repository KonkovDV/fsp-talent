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
  id: string; stem: string; code: string | null; answer_mode?: 'choice' | 'number'
  options: { index: number; text: string }[]
  topic_label: string; is_correct?: boolean; explanation?: string; answered?: boolean
}
interface Mine { id: string; title: string; status: string }
const WHOLE = /^[+\-\u2212]?\d{1,12}$/
const APP_STATUS: Record<string, string> = { applied: 'отправлен', reviewing: 'смотрят', invited: 'зовут на интервью', rejected: 'отказ', closed: 'вакансия закрыта' }
const APP_BADGE: Record<string, string> = { applied: 'badge-vc', reviewing: 'badge-brand', invited: 'badge-ok', rejected: 'badge-warn', closed: 'badge-vc' }

export default function CandidateVacancies() {
  const qc = useQueryClient()
  const [task, setTask] = useState<PracticeItem | null>(null)
  const [picked, setPicked] = useState<number | null>(null)
  const [typed, setTyped] = useState('')
  const [taskError, setTaskError] = useState('')
  const [params] = useSearchParams()
  const topic = params.get('topic')
  const { data: cards = [], isLoading } = useQuery({ queryKey: ['vacanciesForMe'], queryFn: () => vacanciesForMe().then(r => r.data as Card[]) })
  const { data: mine = [] } = useQuery({ queryKey: ['myApplications'], queryFn: () => myApplications().then(r => r.data as Mine[]) })
  const practice = useMutation({
    mutationFn: (opts: { vacancy_id?: string; topic?: string }) => startPractice(opts).then(r => r.data as PracticeItem),
    onSuccess: item => { setTaskError(''); setPicked(null); setTyped(''); setTask(item) },
    onError: (e: unknown) => setTaskError(apiError(e, 'Задание не собрано')),
  })
  useEffect(() => { if (topic) practice.mutate({ topic }) }, [topic])
  const submitPractice = useMutation({
    mutationFn: () => {
      const body = task!.answer_mode === 'number'
        ? { answer_text: typed.replace(/\s/g, '') }
        : { answer_index: picked! }
      return answerPractice(task!.id, body).then(r => r.data as PracticeItem)
    },
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
          {task.code && <pre className="code-block mt-3"><code>{task.code}</code></pre>}
          {task.answer_mode === 'number' ? (
            <form className="mt-4" onSubmit={e => { e.preventDefault(); if (WHOLE.test(typed.replace(/\s/g, '')) && !submitPractice.isPending) submitPractice.mutate() }}>
              <label htmlFor="practice-answer" className="field-label">Ответ — целое число</label>
              <input id="practice-answer" value={typed} onChange={e => setTyped(e.target.value)} disabled={task.answered}
                inputMode="numeric" autoComplete="off" spellCheck={false} maxLength={32} placeholder="например, 42"
                className="input max-w-xs font-mono text-base" />
            </form>
          ) : (
            <ul className="mt-4 grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Варианты ответа">
              {task.options.map(o => (
                <li key={o.index}>
                  <button type="button" role="radio" aria-checked={picked === o.index} disabled={task.answered} onClick={() => setPicked(o.index)}
                    className={`w-full rounded-md border px-4 py-2.5 text-left text-sm transition-colors ${picked === o.index ? 'border-accent bg-accent-soft font-medium text-accent' : 'border-line-strong bg-panel text-ink hover:border-accent'}`}>
                    {o.text}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {task.answered ? (
            <p className={`mt-4 ${task.is_correct ? 'notice-ok' : 'notice-error'}`} role="status"><span><b>{task.is_correct ? 'Верно.' : 'Неверно.'}</b> {task.explanation}</span></p>
          ) : (
            <button type="button" className="btn-primary mt-4"
              disabled={submitPractice.isPending || (task.answer_mode === 'number' ? !WHOLE.test(typed.replace(/\s/g, '')) : picked == null)}
              onClick={() => submitPractice.mutate()}>Ответить</button>
          )}
        </section>
      )}
      {mine.length > 0 && (
        <section className="mb-6">
          <h2 className="section-title">Мои отклики</h2>
          <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-panel">
            {mine.map(a => (
              <li key={a.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                <span className="text-ink">{a.title}</span>
                <span className={APP_BADGE[a.status] ?? 'badge-vc'}>{APP_STATUS[a.status] ?? a.status}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <ul className="space-y-4">
        {cards.map(card => (
          <li key={card.id} className="card p-0">
            <div className="flex flex-wrap items-start gap-4 p-5 sm:p-6">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-accent-soft font-display text-lg font-bold text-accent" aria-hidden>
                {(card.company ?? '?').slice(0, 1)}
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-ink">{card.title}</h2>
                <p className="text-sm text-ink-2">{card.company}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-2">
                  <CategoryPlate role={card.role} grade={card.grade} /> <span>{FORMAT[card.work_format] ?? card.work_format}</span>
                </div>
              </div>
              {(card.salary_from || card.salary_to) && (
                <p className="w-full text-left sm:w-auto sm:text-right">
                  <span className="block font-display text-xl font-bold text-ink num">{rub(card.salary_from)} – {rub(card.salary_to)}</span>
                  <span className="text-xs text-ink-3">до вычета НДФЛ</span>
                </p>
              )}
            </div>
            {(card.matched_skills.length > 0 || card.missing_skills.length > 0 || card.why.length > 0) && (
              <div className="grid gap-4 border-t border-line px-5 py-4 sm:grid-cols-2 sm:px-6">
                <div className="flex flex-wrap content-start gap-1.5">
                  {card.matched_skills.map(sk => <span key={sk} className="chip-active">{sk}</span>)}
                  {card.missing_skills.map(sk => <span key={sk} className="chip-missing">нет {sk}</span>)}
                </div>
                {card.why.length > 0 && (
                  <ul className="space-y-1 text-sm text-ink-2">
                    {card.why.map(l => <li key={l} className="flex gap-2"><span className="text-ok" aria-hidden>+</span>{l}</li>)}
                  </ul>
                )}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3 sm:px-6">
              <button disabled={card.applied || !card.can_apply || apply.isPending} onClick={() => apply.mutate(card.id)}
                className={card.applied ? 'btn-secondary btn-sm' : 'btn-primary btn-sm'}>
                {card.applied ? 'Отклик отправлен' : card.can_apply ? 'Откликнуться' : 'Нужно согласие представителя'}
              </button>
              <Link to={`/candidate/assessment?vacancy=${card.id}`} className="btn-secondary btn-sm">Тест по этой вакансии</Link>
              <button type="button" className="btn-ghost btn-sm" onClick={() => practice.mutate({ vacancy_id: card.id })}>Короткая практика, 1 задание</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
