import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, answerTask, tasksForMe, type CandidateTask } from '../../api/client'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'

const CHECK: Record<string, string> = {
  number: 'Ответ — целое число. Проверит система сразу.',
  choice: 'Один вариант из списка. Проверит система сразу.',
  open: 'Решение или подход к решению, до 4000 знаков. Проверит работодатель.',
  code: 'Функция solve. Скрытые проверки. Грейд и подбор не меняются.',
}

export function TaskResult({ task }: { task: CandidateTask }) {
  const s = task.submission
  if (!s) return null
  if (s.status === 'review') return <span className="badge-warn">на проверке у работодателя</span>
  return <span className={s.passed ? 'badge-ok' : 'badge-vc'}>{s.passed ? 'зачтено' : 'не зачтено'}</span>
}

function AnswerForm({ task }: { task: CandidateTask }) {
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [choice, setChoice] = useState<number | null>(null)
  const [error, setError] = useState('')
  const send = useMutation({
    mutationFn: () => answerTask(task.id, task.answer_type === 'choice' ? { answer_index: choice ?? -1 } : { answer_text: text }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tasksForMe'] }); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: e => setError(apiError(e, 'Ответ не отправлен')),
  })
  const ready = task.answer_type === 'choice' ? choice !== null : text.trim().length > 0
  const submit = (e: React.FormEvent) => { e.preventDefault(); setError(''); if (ready) send.mutate() }
  const id = `ans-${task.id}`
  return (
    <form onSubmit={submit} className="mt-4 space-y-3 border-t border-line pt-4">
      {task.answer_type === 'number' && (
        <div><label className="field-label" htmlFor={id}>Ваш ответ</label>
          <input id={id} value={text} onChange={e => setText(e.target.value)} inputMode="numeric" className="input num w-40" maxLength={40} /></div>
      )}
      {task.answer_type === 'choice' && (
        <fieldset className="space-y-2">
          <legend className="field-label">Выберите ответ</legend>
          {task.options.map(o => (
            <label key={o.index} className={`flex cursor-pointer items-start gap-2.5 rounded-lg border p-3 text-sm ${choice === o.index ? 'border-accent bg-accent-soft' : 'border-line hover:border-line-strong'}`}>
              <input type="radio" name={id} className="mt-0.5" checked={choice === o.index} onChange={() => setChoice(o.index)} />
              <span className="break-words font-mono text-[13px] text-ink">{o.text}</span>
            </label>
          ))}
        </fieldset>
      )}
      {task.answer_type === 'code' && (
        <div><label className="field-label" htmlFor={id}>Функция solve</label>
          <textarea id={id} value={text} onChange={e => setText(e.target.value)} rows={8} maxLength={16384}
            className="input resize-y font-mono text-[13px]" placeholder={'def solve(xs):\n    return 0'} />
          <p className="field-hint">Результат практики. Грейд не меняется.</p></div>
      )}
      {task.answer_type === 'open' && (
        <div><label className="field-label" htmlFor={id}>Решение или подход к решению</label>
          <textarea id={id} value={text} onChange={e => setText(e.target.value)} rows={6} maxLength={4000}
            className="input resize-y" placeholder="Как бы вы решали: шаги, что проверите, код или псевдокод" />
          <p className="field-hint num">{text.length} / 4000</p></div>
      )}
      {error && <p className="notice-error" role="alert">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!ready || send.isPending} className="btn-primary">{send.isPending ? 'Отправляем…' : 'Отправить ответ'}</button>
        <span className="text-xs text-ink-3">Ответ отправляется один раз.</span>
      </div>
    </form>
  )
}

function TaskCard({ task, focused }: { task: CandidateTask; focused: boolean }) {
  const s = task.submission
  return (
    <li id={`task-${task.id}`} className={`card scroll-mt-24 ${focused ? 'ring-2 ring-inset ring-accent' : ''}`} data-testid="employer-task">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-ink-2">
            {task.company ? `«${task.company}»` : 'Работодатель'}{task.addressed ? ', лично вам' : ', для всех кандидатов специализации'}
          </p>
          <h2 className="mt-0.5 text-lg font-semibold text-ink">{task.title}</h2>
          <p className="mt-1 text-xs text-ink-3">{CHECK[task.answer_type]}{task.deadline ? ` Срок — до ${date(task.deadline)}.` : ''}</p>
        </div>
        <TaskResult task={task} />
      </div>
      <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed text-ink">{task.statement}</p>
      {task.vacancy_id && <p className="mt-2 text-sm"><Link to={`/candidate/vacancies?vacancy=${task.vacancy_id}`} className="text-accent hover:underline">Вакансия, к которой относится задание</Link></p>}
      {task.accepts_answers && <AnswerForm task={task} />}
      {s && (
        <div className="mt-4 space-y-1 border-t border-line pt-4 text-sm">
          <p className="text-ink-2">Ваш ответ от {date(s.submitted_at)}:{' '}
            <span className="whitespace-pre-wrap break-words text-ink">{s.answer_index != null ? task.options[s.answer_index]?.text : s.answer_text}</span></p>
          {task.reference != null && !s.passed && <p className="text-ink-2">Эталон: <span className="font-mono text-ink">{task.reference}</span></p>}
          {s.comment && <p className="text-ink-2">Комментарий работодателя: <span className="text-ink">{s.comment}</span></p>}
          {s.passed != null && <p className="text-xs text-ink-3">Результат виден работодателям в вашей карточке как свежий сигнал.</p>}
        </div>
      )}
    </li>
  )
}

/** Tasks from employers: public for the candidate's specialization and those addressed to them. */
export default function CandidateTasks() {
  const [params] = useSearchParams()
  const focus = params.get('task')
  const { data: tasks = [], isLoading, isError, error } = useQuery({ queryKey: ['tasksForMe'], queryFn: () => tasksForMe().then(r => r.data) })
  useEffect(() => {
    if (focus && tasks.length) document.getElementById(`task-${focus}`)?.scrollIntoView({ block: 'start' })
  }, [focus, tasks.length])
  const open = tasks.filter(t => t.accepts_answers)
  const done = tasks.filter(t => !t.accepts_answers)
  return (
    <div className="max-w-3xl">
      <PageHeader title="Задания от работодателей"
        lead="Компании пишут задания сами: одни для всех кандидатов вашей специализации, другие лично вам. Грейд они не меняют, а вердикт с датой работодатели видят в вашей карточке." />
      {isLoading && <Skeleton className="h-48" />}
      {isError && <p className="notice-error mb-4" role="alert">{apiError(error, 'Не удалось загрузить задания')}</p>}
      {!isLoading && !isError && tasks.length === 0 && (
        <Empty title="Заданий пока нет">Задания появляются, когда работодатели публикуют их для вашей специализации или отправляют лично вам. Пока можно решить задачу недели на странице «Обзор».</Empty>
      )}
      {open.length > 0 && <h2 className="mb-3 section-title">Ждут ответа: {open.length}</h2>}
      <ul className="space-y-4">{open.map(t => <TaskCard key={t.id} task={t} focused={t.id === focus} />)}</ul>
      {done.length > 0 && <h2 className="mb-3 mt-8 section-title">Отвеченные</h2>}
      <ul className="space-y-4">{done.map(t => <TaskCard key={t.id} task={t} focused={t.id === focus} />)}</ul>
    </div>
  )
}
