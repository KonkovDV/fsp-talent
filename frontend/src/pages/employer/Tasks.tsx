import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import {
  apiError, closeTask, myTasks, reviewSubmission, taskSubmissions, type EmployerTask, type ReviewedSubmission,
} from '../../api/client'
import TaskDialog from '../../components/TaskDialog'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'
import { ROLE_RU } from '../../labels'

const TYPE_LABEL: Record<string, string> = { number: 'число', choice: 'выбор варианта', open: 'открытый ответ' }

function audience(t: EmployerTask): string {
  return t.visibility === 'addressed' ? 'адресное, одному кандидату' : `всем: ${ROLE_RU[t.specialization ?? ''] ?? t.specialization}`
}

function Verdict({ s }: { s: ReviewedSubmission }) {
  if (s.status === 'review') return <span className="badge-warn">на проверке</span>
  return <span className={s.passed ? 'badge-ok' : 'badge-vc'}>{s.passed ? 'зачтено' : 'не зачтено'}{s.status === 'checked' ? ', система' : ''}</span>
}

function ReviewForm({ s, onDone }: { s: ReviewedSubmission; onDone: () => void }) {
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const review = useMutation({
    mutationFn: (passed: boolean) => reviewSubmission(s.id, passed, comment.trim()),
    onSuccess: onDone,
    onError: e => setError(apiError(e, 'Оценка не сохранена')),
  })
  return (
    <div className="mt-3 space-y-2">
      <label className="field-label" htmlFor={`c-${s.id}`}>Комментарий кандидату, если нужно</label>
      <textarea id={`c-${s.id}`} value={comment} onChange={e => setComment(e.target.value)} rows={2} maxLength={1000}
        className="input resize-y" placeholder="Что получилось и что стоит доработать" />
      <div className="flex flex-wrap gap-2">
        <button onClick={() => review.mutate(true)} disabled={review.isPending} className="btn-primary btn-sm">Зачтено</button>
        <button onClick={() => review.mutate(false)} disabled={review.isPending} className="btn-secondary btn-sm">Не зачтено</button>
      </div>
      {error && <p className="notice-error" role="alert">{error}</p>}
    </div>
  )
}

function Submissions({ task }: { task: EmployerTask }) {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['taskSubmissions', task.id], queryFn: () => taskSubmissions(task.id).then(r => r.data),
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['taskSubmissions', task.id] })
    qc.invalidateQueries({ queryKey: ['employerTasks'] })
  }
  const close = useMutation({ mutationFn: () => closeTask(task.id), onSuccess: refresh })
  const subs = data?.submissions ?? []
  return (
    <section className="card space-y-4" aria-labelledby="task-detail">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="task-detail" className="section-title">{task.title}</h2>
          <p className="mt-1 text-xs text-ink-3">{audience(task)}, ответ: {TYPE_LABEL[task.answer_type]}{task.deadline ? `, до ${date(task.deadline)}` : ''}</p>
        </div>
        {task.is_open && <button onClick={() => close.mutate()} disabled={close.isPending} className="btn-ghost btn-sm">Закрыть приём ответов</button>}
      </div>
      <p className="whitespace-pre-wrap text-sm text-ink">{task.statement}</p>
      {task.answer_type === 'number' && <p className="text-sm text-ink-2">Эталон: <b className="num text-ink">{task.reference_number}</b></p>}
      {task.answer_type === 'choice' && (
        <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-2">
          {task.options.map((o, i) => <li key={i} className={i === task.correct_index ? 'font-medium text-ok' : ''}>{o}{i === task.correct_index ? ' — верный' : ''}</li>)}
        </ol>
      )}
      <h3 className="border-t border-line pt-4 text-sm font-semibold text-ink">Ответы{subs.length ? `: ${subs.length}` : ''}</h3>
      {isLoading && <Skeleton className="h-20" />}
      {!isLoading && subs.length === 0 && <p className="text-sm text-ink-2">Ответов пока нет.</p>}
      <ul className="space-y-3">
        {subs.map(s => (
          <li key={s.id} className="panel-quiet" data-testid="submission">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-ink">Кандидат: {s.candidate}</span>
              <span className="flex items-center gap-2 text-xs text-ink-3">{date(s.submitted_at)} <Verdict s={s} /></span>
            </div>
            {s.answer_text && <p className="mt-2 whitespace-pre-wrap break-words text-sm text-ink">{s.answer_text}</p>}
            {s.answer_index != null && <p className="mt-2 text-sm text-ink">Выбран вариант: {task.options[s.answer_index]}</p>}
            {s.comment && <p className="mt-2 text-xs text-ink-2">Ваш комментарий: {s.comment}</p>}
            {s.status === 'review' && <ReviewForm s={s} onDone={refresh} />}
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Tasks the employer writes (TZ 2.1, regular tasks): publish, see answers, review open ones. */
export default function EmployerTasks() {
  const [params, setParams] = useSearchParams()
  const { data: tasks = [], isLoading } = useQuery({ queryKey: ['employerTasks'], queryFn: () => myTasks().then(r => r.data) })
  const [creating, setCreating] = useState(false)
  const selectedId = params.get('task') ?? tasks[0]?.id
  const selected = tasks.find(t => t.id === selectedId)
  useEffect(() => {
    if (params.get('task') && !isLoading && tasks.length && !selected) setParams({}, { replace: true })
  }, [params, isLoading, tasks.length, selected, setParams])
  const waiting = tasks.reduce((n, t) => n + t.awaiting_review, 0)

  return (
    <div>
      <PageHeader title="Задания"
        lead="Регулярные задания от вашей компании. Ответ-число и выбор варианта проверяет система по эталону, открытые ответы проверяете вы. Вердикт виден в анонимной карточке кандидата."
        actions={<button onClick={() => setCreating(true)} className="btn-primary"><Plus size={16} aria-hidden /> Новое задание</button>} />
      {tasks.length > 0 && (
        <dl className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="stat-card"><dt className="stat-card-label">Заданий</dt><dd className="stat-card-value">{tasks.length}</dd></div>
          <div className="stat-card"><dt className="stat-card-label">Открыто</dt><dd className="stat-card-value">{tasks.filter(t => t.accepts_answers).length}</dd></div>
          <div className="stat-card"><dt className="stat-card-label">Ответов</dt><dd className="stat-card-value">{tasks.reduce((n, t) => n + t.submissions, 0)}</dd></div>
          <div className="stat-card"><dt className="stat-card-label">Ждут проверки</dt><dd className="stat-card-value">{waiting}</dd></div>
        </dl>
      )}
      {isLoading && <Skeleton className="h-40" />}
      {!isLoading && tasks.length === 0 && (
        <Empty title="Заданий пока нет" action={<button onClick={() => setCreating(true)} className="btn-primary">Написать задание</button>}>
          Опубликуйте задание для всех кандидатов специализации или отправьте его одному кандидату из поиска кнопкой «Дать задание».
        </Empty>
      )}
      {tasks.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <ul className="space-y-2" aria-label="Список заданий">
            {tasks.map(t => (
              <li key={t.id}>
                <button onClick={() => setParams({ task: t.id })} aria-current={t.id === selectedId ? 'true' : undefined}
                  className={`w-full rounded-lg border p-4 text-left transition-colors ${t.id === selectedId ? 'border-accent bg-accent-soft' : 'border-line bg-panel hover:border-line-strong'}`}>
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0 font-medium text-ink">{t.title}</span>
                    {t.awaiting_review > 0 && <span className="badge-warn shrink-0">ждут: {t.awaiting_review}</span>}
                  </span>
                  <span className="mt-1 block text-xs text-ink-2">{audience(t)}, {TYPE_LABEL[t.answer_type]}</span>
                  <span className="mt-1 block text-xs text-ink-3">
                    Ответов {t.submissions}{t.answer_type !== 'open' || t.passed ? `, зачтено ${t.passed}` : ''}
                    {t.accepts_answers ? '' : ', приём закрыт'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selected && <Submissions key={selected.id} task={selected} />}
        </div>
      )}
      {creating && <TaskDialog onClose={() => setCreating(false)} />}
    </div>
  )
}
