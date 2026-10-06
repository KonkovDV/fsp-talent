import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ExamPreview, { type Exam } from '../../components/ExamPreview'
import { apiError, applicationContacts, closeVacancy, createVacancy, getMyVacancies, previewVacancyExam, updateApplicationStatus, updateVacancy, vacancyApplications } from '../../api/client'
import { DISC_RU, GRADES, ROLE_RU, gradeRu } from '../../labels'
import { CategoryPlate, Empty, PageHeader, date, rub } from '../../components/ui'

const EMPTY = { title: '', description: '', role: 'backend', grade: 'middle', discipline: '', min_rank: '', skills: '', salary_from_gross: 150000,
  salary_to_gross: 250000, work_format: 'remote', allows_minors: false }
interface Vacancy { id: string; title: string; description?: string | null; role: string | null; grade: string | null
  discipline?: string | null; min_rank?: string | null; allows_minors?: boolean; is_open: boolean; skills: string[]
  salary_from: number | null; salary_to: number | null; work_format: string }
interface Application { id: string; vacancy_title: string; status: string; created_at: string | null }
const APP_STATUS: Record<string, string> = {
  applied: 'отклик', reviewing: 'смотрим', invited: 'приглашён', rejected: 'отказ', closed: 'закрыт',
}
const FORMAT: Record<string, string> = { remote: 'удалённо', hybrid: 'гибрид', office: 'в офисе' }

/** The second path of the TZ: a published vacancy that candidates can apply to themselves. */
export default function EmployerVacancies() {
  const qc = useQueryClient()
  const [form, setForm] = useState(EMPTY)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [statusError, setStatusError] = useState('')
  const [exam, setExam] = useState<Exam | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [contacts, setContacts] = useState<Record<string, string>>({})
  const { data: vacancies = [] } = useQuery<Vacancy[]>({ queryKey: ['myVacancies'], queryFn: () => getMyVacancies().then(r => r.data) })
  const { data: applications = [] } = useQuery<Application[]>({ queryKey: ['applications'], queryFn: () => vacancyApplications().then(r => r.data) })
  const payload = () => ({ ...form, skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
    discipline: form.discipline || null, min_rank: form.min_rank || null, description: form.description || null })
  const create = useMutation({
    mutationFn: () => editing ? updateVacancy(editing, payload()) : createVacancy(payload()),
    onSuccess: () => { setError(''); setExam(null); setOpen(false); setEditing(null); setForm(EMPTY); qc.invalidateQueries({ queryKey: ['myVacancies'] }) },
    onError: e => setError(apiError(e, 'Вакансия не сохранена')),
  })
  const setAppStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateApplicationStatus(id, status),
    onSuccess: () => { setStatusError(''); qc.invalidateQueries({ queryKey: ['applications'] }) },
    onError: e => setStatusError(apiError(e, 'Статус не изменён')),
  })
  const close = useMutation({ mutationFn: (id: string) => closeVacancy(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['myVacancies'] }) })
  const reveal = useMutation({
    mutationFn: (id: string) => applicationContacts(id).then(r => ({ id, d: r.data })),
    onSuccess: ({ id, d }) => setContacts(prev => ({ ...prev, [id]: [d.display_name, d.email, d.telegram].filter(Boolean).join(', ') })),
  })
  const preview = useMutation({
    mutationFn: () => previewVacancyExam({ ...form, skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
      discipline: form.discipline || null, description: form.description || null }).then(r => r.data as Exam),
    onSuccess: data => { setError(''); setExam(data) },
    onError: e => setError(apiError(e, 'Не удалось собрать тест')),
  })
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : k.startsWith('salary') ? Number(e.target.value) : e.target.value })

  return (
    <div>
      <PageHeader title="Вакансии" lead="Опубликованная вакансия видна подходящим кандидатам, и они могут откликнуться сами. Зарплатная вилка обязательна."
        actions={!open && <button onClick={() => { setEditing(null); setForm(EMPTY); setOpen(true) }} className="btn-primary">Новая вакансия</button>} />

      {open && (
        <form className="card mb-8 space-y-5" onSubmit={e => { e.preventDefault(); create.mutate() }}>
          <div><label className="field-label" htmlFor="v-title">Название</label>
            <input id="v-title" className="input" value={form.title} onChange={set('title')} placeholder="Backend-разработчик в команду платежей" /></div>
          <div><label className="field-label" htmlFor="v-desc">Описание</label>
            <textarea id="v-desc" className="input min-h-24" value={form.description} onChange={set('description')}
              placeholder="Сервисы на Python и PostgreSQL, разбор платежей, код-ревью" /></div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div><label className="field-label" htmlFor="v-role">Специализация</label>
              <select id="v-role" className="select" value={form.role} onChange={set('role')}>
                {Object.entries(ROLE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div><label className="field-label" htmlFor="v-grade">Грейд</label>
              <select id="v-grade" className="select" value={form.grade} onChange={set('grade')}>
                {GRADES.map(g => <option key={g} value={g}>{gradeRu(g)}</option>)}</select></div>
            <div><label className="field-label" htmlFor="v-format">Формат</label>
              <select id="v-format" className="select" value={form.work_format} onChange={set('work_format')}>
                {Object.entries(FORMAT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="sm:col-span-1"><label className="field-label" htmlFor="v-skills">Навыки</label>
              <input id="v-skills" className="input" value={form.skills} onChange={set('skills')} placeholder="Python, PostgreSQL" /></div>
            <div><label className="field-label" htmlFor="v-from">Зарплата от, ₽</label>
              <input id="v-from" type="number" step={5000} className="input num" value={form.salary_from_gross} onChange={set('salary_from_gross')} /></div>
            <div><label className="field-label" htmlFor="v-to">Зарплата до, ₽</label>
              <input id="v-to" type="number" step={5000} className="input num" value={form.salary_to_gross} onChange={set('salary_to_gross')} /></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div><label className="field-label" htmlFor="v-disc">Дисциплина ФСП, если важна</label>
              <select id="v-disc" className="select" value={form.discipline} onChange={set('discipline')}>
                <option value="">Не важна</option>{Object.entries(DISC_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <label className="flex items-end gap-2 pb-3 text-sm text-ink sm:col-span-2">
              <input type="checkbox" checked={form.allows_minors} onChange={set('allows_minors')} />Можно кандидатам 16–17 лет (с согласия родителей)</label>
          </div>
          {error && <p className="notice-error" role="alert">{error}</p>}
          <div className="flex gap-3">
            <button className="btn-primary" type="submit" disabled={create.isPending || form.title.length < 3}>{editing ? 'Сохранить' : 'Опубликовать'}</button>
            <button type="button" className="btn-secondary" disabled={preview.isPending || form.title.length < 3}
              onClick={() => preview.mutate()}>Какой тест получится</button>
            <button type="button" className="btn-secondary" onClick={() => { setOpen(false); setExam(null); setEditing(null) }}>Отмена</button>
          </div>
          {exam && <div className="rounded-lg border border-line bg-sunken/60 p-4"><ExamPreview exam={exam} /></div>}
        </form>
      )}

      {vacancies.length === 0 && !open ? <Empty title="Вакансий пока нет">Это необязательный путь: основная механика — приглашения из подборки.</Empty> : (
        <ul className="space-y-3">
          {vacancies.map(v => (
            <li key={v.id} className="card flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="font-medium text-ink">{v.title}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
                  <CategoryPlate role={v.role} grade={v.grade} /><span>{FORMAT[v.work_format] ?? v.work_format}</span>
                  {v.skills.map(s => <span key={s} className="chip-default">{s}</span>)}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="num text-sm text-ink">{rub(v.salary_from)} – {rub(v.salary_to)}</span>
                {v.is_open && <button className="btn-ghost btn-sm" onClick={() => {
                  setEditing(v.id); setOpen(true); setExam(null)
                  setForm({ ...EMPTY, title: v.title, description: v.description ?? '', role: v.role ?? 'backend', grade: v.grade ?? 'middle',
                    discipline: v.discipline ?? '', min_rank: v.min_rank ?? '', allows_minors: Boolean(v.allows_minors),
                    skills: v.skills.join(', '), salary_from_gross: v.salary_from ?? 150000, salary_to_gross: v.salary_to ?? 250000,
                    work_format: v.work_format })
                }}>Изменить</button>}
                {v.is_open ? <button className="btn-ghost btn-sm" onClick={() => close.mutate(v.id)}>Закрыть</button> : <span className="badge-vc">закрыта</span>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <section className="mt-10">
        <h2 className="section-title">Отклики</h2>
        {statusError && <p className="notice-error mt-3" role="alert">{statusError}</p>}
        {applications.length === 0 ? <p className="mt-3 text-sm text-ink-2">Откликов пока нет.</p> : (
          <div className="card mt-4 overflow-x-auto p-0">
            <table className="protocol">
              <thead><tr><th>Вакансия</th><th>Дата</th><th>Статус</th><th>Контакты</th></tr></thead>
              <tbody>
                {applications.map(a => (
                  <tr key={a.id}>
                    <td className="text-ink">{a.vacancy_title}</td>
                    <td className="num text-ink-2">{date(a.created_at)}</td>
                    <td>
                      <select className="select" value={a.status} aria-label={`Статус отклика ${a.vacancy_title}`}
                        disabled={a.status === 'rejected' || a.status === 'accepted'}
                        onChange={e => setAppStatus.mutate({ id: a.id, status: e.target.value })}>
                        {Object.entries(APP_STATUS).filter(([k]) => k === a.status || k !== 'applied')
                          .map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                      </select>
                    </td>
                    <td>{contacts[a.id] ? <span className="text-ink">{contacts[a.id]}</span>
                      : <button className="btn-secondary btn-sm" onClick={() => reveal.mutate(a.id)}>Показать контакты</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
