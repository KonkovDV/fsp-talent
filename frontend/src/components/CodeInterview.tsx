import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, disputeInterviewCode, getInterviewCode, labProblems, openInterviewCode, saveInterviewCode } from '../api/client'

interface Shot { version: number; text: string }
interface CodeTask {
  problem: { id: string; title: string; statement: string } | null
  prompt: string
  draft: string
  version: number
  snapshots: Shot[]
  dispute: string | null
}

/** A coding step after the candidate has accepted. Drafts are saved. A dispute does not change the grade. */
export default function CodeInterview({ offerId, side }: { offerId: string; side: 'employer' | 'participant' }) {
  const qc = useQueryClient()
  const task = useQuery<CodeTask | null>({
    queryKey: ['interviewCode', offerId],
    queryFn: () => getInterviewCode(offerId).then(r => r.data ?? null),
    retry: false,
  })
  // The API answers null while the company has not given a task yet.
  const noTask = task.isSuccess && task.data == null
  const library = useQuery({
    queryKey: ['labProblems'],
    queryFn: () => labProblems().then(r => r.data),
    enabled: side === 'employer' && noTask,
  })
  const [problemId, setProblemId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [text, setText] = useState('')
  const [slide, setSlide] = useState(0)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const data = task.data
    if (!data) return
    setText(data.draft)
    setSlide(Math.max(0, data.snapshots.length - 1))
  }, [task.data])

  const save = useMutation({
    mutationFn: (body: { text: string; version: number }) => saveInterviewCode(offerId, body.text, body.version),
    onSuccess: (res) => {
      setError('')
      qc.setQueryData(['interviewCode', offerId], res.data)
    },
    onError: (e: unknown) => setError(apiError(e, 'Черновик не сохранился')),
  })

  useEffect(() => {
    if (side !== 'participant' || !task.data || text === task.data.draft) return
    const current = task.data.version
    const handle = window.setTimeout(() => save.mutate({ text, version: current }), 400)
    return () => window.clearTimeout(handle)
  }, [text, task.data, side])

  const open = useMutation({
    mutationFn: () => openInterviewCode(offerId, { problem_id: problemId || null, prompt }),
    onSuccess: () => { setError(''); qc.invalidateQueries({ queryKey: ['interviewCode', offerId] }) },
    onError: (e: unknown) => setError(apiError(e, 'Задание не открылось')),
  })
  const dispute = useMutation({
    mutationFn: () => disputeInterviewCode(offerId, note),
    onSuccess: () => { setError(''); setNote(''); qc.invalidateQueries({ queryKey: ['interviewCode', offerId] }) },
    onError: (e: unknown) => setError(apiError(e, 'Пометка не сохранилась')),
  })

  const data = task.data
  const shots = data?.snapshots ?? []
  const shown = shots[slide]

  return (
    <section className="space-y-2 border-t border-line pt-3" data-testid="code-interview">
      <h3 className="text-sm font-medium text-ink">Задание на код</h3>
      <p className="text-xs text-ink-3">Черновик сохраняется сам. Пометка о споре не меняет грейд и не считается моделью.</p>
      {error && <p className="text-sm text-danger" role="alert">{error}</p>}
      {noTask && side === 'employer' && (
        <div className="space-y-2">
          <select className="field" value={problemId} onChange={e => setProblemId(e.target.value)} aria-label="Задание из библиотеки">
            <option value="">Своё условие</option>
            {(library.data ?? []).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
          <textarea className="field min-h-20" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Условие, если своего задания нет в библиотеке" />
          <button type="button" className="btn-secondary btn-sm" disabled={open.isPending} onClick={() => open.mutate()}>Дать задание</button>
        </div>
      )}
      {noTask && side === 'participant' && <p className="text-sm text-ink-2">Компания ещё не дала задание.</p>}
      {task.isError && <p className="text-sm text-danger" role="alert">{apiError(task.error, 'Задание не загрузилось')}</p>}
      {data && (
        <div className="space-y-2">
          {data.problem && <p className="text-sm text-ink"><b>{data.problem.title}.</b> {data.problem.statement}</p>}
          {data.prompt && <p className="text-sm text-ink-2">{data.prompt}</p>}
          {shots.length > 1 && (
            <label className="block text-xs text-ink-3">
              Снимок {shown?.version ?? ''}
              <input className="mt-1 block w-full" type="range" min={0} max={shots.length - 1} value={slide}
                onChange={e => setSlide(Number(e.target.value))} />
            </label>
          )}
          {shown && shown.version !== data.version && <pre className="overflow-x-auto text-xs text-ink-2">{shown.text}</pre>}
          {side === 'participant' ? (
            <textarea className="field min-h-24 font-mono text-sm" value={text} onChange={e => setText(e.target.value)} aria-label="Черновик решения" />
          ) : (
            <pre className="overflow-x-auto text-sm text-ink">{data.draft || 'Черновика ещё нет.'}</pre>
          )}
          {data.dispute && <p className="text-sm text-ink-2">Пометка кандидата: {data.dispute}</p>}
          {side === 'participant' && !data.dispute && (
            <div className="flex flex-wrap gap-2">
              <input className="field" value={note} onChange={e => setNote(e.target.value)} placeholder="Что в условии не так" aria-label="Пометка к заданию" />
              <button type="button" className="btn-ghost btn-sm" disabled={note.trim().length < 10 || dispute.isPending} onClick={() => dispute.mutate()}>Отметить спор</button>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
