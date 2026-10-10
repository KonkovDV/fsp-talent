import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { addResume, apiError, deleteResume, listResumes, updateResume, type ResumeBody, type ResumeRow } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'

const EMPTY: ResumeBody = { specialization: '', grade: 'junior', stack: [], summary: null }

/** The survey specialization plus up to two more. An extra grade is declared until a test confirms it. */
export default function ResumesCard() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['resumes'], queryFn: () => listResumes().then(r => r.data) })
  const [form, setForm] = useState<ResumeBody | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [stackText, setStackText] = useState('')
  const [error, setError] = useState('')
  const done = (next: unknown) => {
    qc.setQueryData(['resumes'], next)
    setForm(null)
    setEditing(null)
    setError('')
  }
  const save = useMutation({
    mutationFn: (body: ResumeBody) => (editing ? updateResume(editing, body) : addResume(body)).then(r => r.data),
    onSuccess: done,
    onError: (e: unknown) => setError(apiError(e, 'Резюме не сохранено')),
  })
  const remove = useMutation({
    mutationFn: (id: string) => deleteResume(id).then(r => r.data),
    onSuccess: done,
    onError: (e: unknown) => setError(apiError(e, 'Резюме не удалено')),
  })

  if (!data) return null
  const taken = new Set([data.primary?.specialization, ...data.extras.map(r => r.specialization)])
  const canAdd = !!data.primary && data.extras.length < data.extra_max
  const open = (row?: ResumeRow) => {
    setError('')
    setEditing(row?.id ?? null)
    setForm(row ? { specialization: row.specialization, grade: row.grade ?? 'junior', stack: row.stack ?? [], summary: row.summary ?? null } : EMPTY)
    setStackText((row?.stack ?? []).join(', '))
  }
  const submit = () => {
    if (!form) return
    const stack = stackText.split(',').map(s => s.trim()).filter(Boolean)
    save.mutate({ ...form, stack, summary: form.summary?.trim() || null })
  }

  return (
    <section className="card space-y-4" aria-labelledby="resumes-h" data-testid="resumes-card">
      <div>
        <h2 id="resumes-h" className="section-title">Резюме</h2>
        <p className="mt-1 text-sm text-ink-2">
          До {data.extra_max + 1} резюме: основное из опроса и ещё по одной специализации на каждое.
          Грейд в дополнительном резюме заявлен; тест по этой специализации его подтвердит.
        </p>
      </div>
      <ul className="space-y-2 text-sm">
        {data.primary && (
          <li className="panel-quiet">
            <span className="font-medium text-ink">{ROLE_RU[data.primary.specialization] ?? data.primary.label}</span>
            {data.primary.grade ? `, ${gradeRu(data.primary.grade)}` : ''}
            <span className="text-ink-3"> · основное, {data.primary.grade_source === 'assessed' ? 'подтверждено тестом' : 'из опроса'}</span>
          </li>
        )}
        {data.extras.map(row => (
          <li key={row.id} className="panel-quiet space-y-1" data-testid="resume-extra">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span><span className="font-medium text-ink">{ROLE_RU[row.specialization] ?? row.label}</span>, {gradeRu(row.grade)}
                <span className="text-ink-3"> · заявлено</span></span>
              <span className="flex gap-2">
                <button type="button" className="btn-ghost btn-sm px-0 text-accent" onClick={() => open(row)}>Изменить</button>
                <button type="button" className="btn-ghost btn-sm px-0 text-danger" disabled={remove.isPending}
                  onClick={() => row.id && remove.mutate(row.id)}>Удалить</button>
              </span>
            </div>
            {!!row.stack?.length && <p className="text-xs text-ink-2">{row.stack.join(', ')}</p>}
            {row.summary && <p className="text-xs text-ink-2">{row.summary}</p>}
          </li>
        ))}
      </ul>
      {!data.primary && <p className="text-sm text-ink-3">Сначала пройдите опрос: он задаёт основное резюме.</p>}
      {form ? (
        <form className="space-y-3" onSubmit={e => { e.preventDefault(); submit() }}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div><label className="field-label" htmlFor="resume-spec">Специализация</label>
              <select id="resume-spec" className="input" value={form.specialization}
                onChange={e => setForm({ ...form, specialization: e.target.value })}>
                <option value="">Выберите</option>
                {Object.entries(ROLE_RU).filter(([code]) => !taken.has(code) || code === form.specialization).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select></div>
            <div><label className="field-label" htmlFor="resume-grade">Грейд</label>
              <select id="resume-grade" className="input" value={form.grade}
                onChange={e => setForm({ ...form, grade: e.target.value })}>
                {GRADES.map(g => <option key={g} value={g}>{gradeRu(g)}</option>)}
              </select></div>
          </div>
          <div><label className="field-label" htmlFor="resume-stack">Стек через запятую</label>
            <input id="resume-stack" className="input" value={stackText} onChange={e => setStackText(e.target.value)}
              placeholder="Kotlin, Jetpack Compose" /></div>
          <div><label className="field-label" htmlFor="resume-summary">Коротко об опыте</label>
            <textarea id="resume-summary" className="input" rows={3} maxLength={600} value={form.summary ?? ''}
              onChange={e => setForm({ ...form, summary: e.target.value })}
              placeholder="Без имени и контактов: их увидит только компания, чьё приглашение вы приняли" /></div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary btn-sm" disabled={!form.specialization || save.isPending}>
              {save.isPending ? 'Сохраняем…' : 'Сохранить резюме'}
            </button>
            <button type="button" className="btn-ghost btn-sm" onClick={() => { setForm(null); setEditing(null) }}>Отмена</button>
          </div>
        </form>
      ) : canAdd && (
        <button type="button" className="btn-secondary btn-sm" onClick={() => open()}>Добавить резюме</button>
      )}
      {error && <p className="notice-error text-sm" role="alert">{error}</p>}
    </section>
  )
}
