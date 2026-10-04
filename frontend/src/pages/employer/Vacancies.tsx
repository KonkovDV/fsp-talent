import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, applicationContacts, closeVacancy, createVacancy, getMyVacancies, vacancyApplications } from '../../api/client'

const empty = { title: '', role: 'backend', grade: 'middle', discipline: 'algorithmic', skills: 'Python, FastAPI',
  salary_from_gross: 150000, salary_to_gross: 250000, work_format: 'remote', allows_minors: false }

export default function EmployerVacancies() {
  const qc = useQueryClient()
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')
  const [contacts, setContacts] = useState<Record<string, string>>({})
  const { data: vacancies = [] } = useQuery({ queryKey: ['myVacancies'], queryFn: () => getMyVacancies().then(r => r.data) })
  const { data: applications = [] } = useQuery({ queryKey: ['applications'], queryFn: () => vacancyApplications().then(r => r.data) })
  const create = useMutation({
    mutationFn: () => createVacancy({
      ...form,
      skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
      role: form.role || null,
      grade: form.grade || null,
      discipline: form.discipline || null,
    }),
    onSuccess: () => { setError(''); qc.invalidateQueries({ queryKey: ['myVacancies'] }) },
    onError: (e) => setError(apiError(e, 'Не удалось опубликовать')),
  })
  const close = useMutation({
    mutationFn: (id: string) => closeVacancy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVacancies'] }),
  })
  const reveal = useMutation({
    mutationFn: (id: string) => applicationContacts(id).then(r => r.data),
    onSuccess: (data, id) => setContacts(prev => ({ ...prev, [id]: `${data.display_name} · ${data.email}` })),
  })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Вакансии</h1>
      <form className="card grid sm:grid-cols-2 gap-3" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
        <input className="border rounded-xl px-3 py-2 text-sm" placeholder="Название" value={form.title}
          onChange={e => setForm({ ...form, title: e.target.value })} />
        <input className="border rounded-xl px-3 py-2 text-sm" placeholder="Навыки через запятую" value={form.skills}
          onChange={e => setForm({ ...form, skills: e.target.value })} />
        <input className="border rounded-xl px-3 py-2 text-sm" placeholder="Роль" value={form.role}
          onChange={e => setForm({ ...form, role: e.target.value })} />
        <input className="border rounded-xl px-3 py-2 text-sm" placeholder="Грейд" value={form.grade}
          onChange={e => setForm({ ...form, grade: e.target.value })} />
        <input className="border rounded-xl px-3 py-2 text-sm" placeholder="Дисциплина" value={form.discipline}
          onChange={e => setForm({ ...form, discipline: e.target.value })} />
        <label className="text-sm flex items-center gap-2">
          <input type="checkbox" checked={form.allows_minors} onChange={e => setForm({ ...form, allows_minors: e.target.checked })} />
          Можно 16–17 лет
        </label>
        {error && <p className="text-sm text-fsp-red sm:col-span-2">{error}</p>}
        <button className="btn-primary text-sm sm:col-span-2" type="submit" disabled={create.isPending}>Опубликовать</button>
      </form>
      <ul className="space-y-2">
        {vacancies.map((v: { id: string; title: string; is_open: boolean; skills: string[] }) => (
          <li key={v.id} className="card flex items-center justify-between">
            <span>{v.title} · {v.skills.join(', ')} · {v.is_open ? 'открыта' : 'закрыта'}</span>
            {v.is_open && <button className="text-sm text-text-muted" onClick={() => close.mutate(v.id)}>Закрыть</button>}
          </li>
        ))}
      </ul>
      <h2 className="text-lg font-semibold">Отклики</h2>
      <ul className="space-y-2">
        {applications.map((a: { id: string; vacancy_title: string }) => (
          <li key={a.id} className="card flex items-center justify-between gap-4">
            <span className="text-sm">{a.vacancy_title}</span>
            {contacts[a.id]
              ? <span className="text-sm">{contacts[a.id]}</span>
              : <button className="btn-primary text-sm" onClick={() => reveal.mutate(a.id)}>Контакты</button>}
          </li>
        ))}
      </ul>
    </div>
  )
}
