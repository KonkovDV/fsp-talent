import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import {
  apiError, compareNeed, needExam, createNeed, listNeeds, needMatches, needShortlist, removeShortlist, setShortlist, surveyOptions, updateNeed,
} from '../../api/client'
import CandidateCard, { type CandidateCardData } from '../../components/CandidateCard'
import InviteDialog from '../../components/InviteDialog'
import TaskDialog from '../../components/TaskDialog'
import ExamPreview, { type Exam } from '../../components/ExamPreview'
import { Empty, PageHeader, Skeleton, date } from '../../components/ui'
import { ROLE_RU, gradeRu } from '../../labels'

interface NeedParams {
  role: string | null; grade: string | null; skills: string[]; nice_to_have: string[]
  industry: string | null; work_goal: string | null; has_fsp: boolean | null
}
interface Need { id: string; title: string; version: number; params: NeedParams; shortlist_count: number }

const EMPTY = { title: '', role: '', grade: '', skills: '', nice: '', industry: '', internship: false }
const csv = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

/** Employer needs: what we look for (versioned), explainable matches, recommended categories, shortlist. */
export default function EmployerNeeds() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const [error, setError] = useState('')
  const [offerFor, setOfferFor] = useState<string | null>(null)
  const [taskFor, setTaskFor] = useState<string | null>(null)
  const [tab, setTab] = useState<'matches' | 'shortlist' | 'exam'>('matches')
  const [picked, setPicked] = useState<string[]>([])
  const [sent, setSent] = useState(false)

  const { data: opts } = useQuery({ queryKey: ['surveyOptions'], queryFn: () => surveyOptions().then(r => r.data) })
  const { data: needs = [] } = useQuery<Need[]>({ queryKey: ['needs'], queryFn: () => listNeeds().then(r => r.data) })
  useEffect(() => { if (!selected && needs.length) setSelected(needs[0].id) }, [needs, selected])
  const current = needs.find(n => n.id === selected) ?? null
  const matches = useQuery({ queryKey: ['needMatches', selected, current?.version], enabled: !!selected,
    queryFn: () => needMatches(selected!).then(r => r.data) })
  const compared = useQuery({
    queryKey: ['needCompare', selected, picked.join(',')],
    enabled: !!selected && picked.length >= 2,
    queryFn: () => compareNeed(selected!, picked).then(r => r.data as { items: { candidate_id: string; role: string; grade: string; score: number; factors: { key: string; label: string; value: number | null }[] }[] }),
  })
  const exam = useQuery({ queryKey: ['needExam', selected, current?.version], enabled: !!selected && tab === 'exam',
    queryFn: () => needExam(selected!).then(r => r.data as Exam) })
  const shortlist = useQuery({ queryKey: ['needShortlist', selected], enabled: !!selected,
    queryFn: () => needShortlist(selected!).then(r => r.data) })

  const body = () => ({
    title: form.title,
    params: { role: form.role || null, grade: form.grade || null, skills: csv(form.skills), nice_to_have: csv(form.nice),
      industry: form.industry || null, work_goal: form.internship ? 'internship' : null },
  })
  const save = useMutation({
    mutationFn: () => (editing === 'new' ? createNeed(body()) : updateNeed(editing!, body())).then(r => r.data),
    onSuccess: (need: Need) => {
      setEditing(null); setSelected(need.id); setError('')
      qc.invalidateQueries({ queryKey: ['needs'] })
    },
    onError: (e: unknown) => setError(apiError(e)),
  })
  const toggle = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => on ? setShortlist(selected!, id) : removeShortlist(selected!, id),
    onSuccess: () => {
      for (const k of ['needMatches', 'needShortlist', 'needs']) qc.invalidateQueries({ queryKey: [k] })
    },
  })
  const edit = (n: Need) => {
    setEditing(n.id)
    setForm({ title: n.title, role: n.params.role ?? '', grade: n.params.grade ?? '', skills: n.params.skills.join(', '),
      nice: n.params.nice_to_have.join(', '), industry: n.params.industry ?? '', internship: n.params.work_goal === 'internship' })
  }
  const field = 'field-label'
  const shortItems = shortlist.data?.items ?? []

  return (
    <div>
      <PageHeader title="Потребности"
        lead="Опишите, кого ищете. Каждое изменение сохраняется новой версией, а шорт-лист помнит, по какой версии выбран кандидат."
        actions={<button onClick={() => { setEditing('new'); setForm(EMPTY) }} className="btn-primary"><Plus size={16} aria-hidden />Новая потребность</button>} />

      {editing && (
        <form className="card mb-8 space-y-5" onSubmit={e => { e.preventDefault(); save.mutate() }} aria-label="Потребность">
          <h2 className="section-title">{editing === 'new' ? 'Новая потребность' : 'Изменение — будет сохранено новой версией'}</h2>
          <div><label className={field} htmlFor="n-title">Название</label>
            <input id="n-title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })}
              placeholder="Например, Python-бэкенд в платёжную команду" className="input" aria-label="Название" /></div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div><label className={field} htmlFor="n-role">Специализация</label>
              <select id="n-role" value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="select" aria-label="Специализация">
                <option value="">Любая</option>
                {Object.entries(opts?.specializations ?? {}).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
              </select></div>
            <div><label className={field} htmlFor="n-grade">Грейд</label>
              <select id="n-grade" value={form.grade} onChange={e => setForm({ ...form, grade: e.target.value })} className="select" aria-label="Грейд">
                <option value="">Любой</option>
                {(opts?.grades ?? []).map((g: string) => <option key={g} value={g}>{gradeRu(g)}</option>)}
              </select></div>
            <div><label className={field} htmlFor="n-ind">Предметная область (необязательно)</label>
              <select id="n-ind" value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} className="select">
                <option value="">Не важна</option>
                {Object.entries(opts?.industries ?? {}).filter(([k]) => k !== 'any').map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
              </select></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className={field} htmlFor="n-req">Обязательные навыки</label>
              <input id="n-req" value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} placeholder="Python, PostgreSQL" className="input" aria-label="Обязательные навыки" /></div>
            <div><label className={field} htmlFor="n-nice">Желательные навыки</label>
              <input id="n-nice" value={form.nice} onChange={e => setForm({ ...form, nice: e.target.value })} placeholder="Docker, Kafka" className="input" aria-label="Желательные навыки" />
              <p className="field-hint">Весят вдвое меньше обязательных.</p></div>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink"><input type="checkbox" checked={form.internship} onChange={e => setForm({ ...form, internship: e.target.checked })} />Ищем стажёра или практиканта</label>
          {error && <p className="notice-error" role="alert">{error}</p>}
          <div className="flex gap-3">
            <button className="btn-primary" disabled={form.title.length < 2 || save.isPending}>{editing === 'new' ? 'Создать' : 'Сохранить новую версию'}</button>
            <button type="button" className="btn-secondary" onClick={() => setEditing(null)}>Отмена</button>
          </div>
        </form>
      )}

      {needs.length === 0 && !editing && (
        <Empty title="Потребностей пока нет" action={<button onClick={() => { setEditing('new'); setForm(EMPTY) }} className="btn-primary">Создать первую</button>}>
          Подборка с объяснением появится сразу после сохранения.
        </Empty>
      )}

      {needs.length > 0 && (
        <div className="grid items-start gap-8 lg:grid-cols-[260px_1fr]">
          <nav aria-label="Потребности" className="lg:sticky lg:top-36">
            <ul className="space-y-1">
              {needs.map(n => (
                <li key={n.id}>
                  <button type="button" aria-current={n.id === selected ? 'true' : undefined} onClick={() => { setSelected(n.id); setTab('matches') }}
                    className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${n.id === selected ? 'bg-panel ring-1 ring-line-strong' : 'hover:bg-panel'}`}>
                    <span className="block text-sm font-medium text-ink">{n.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-3">версия {n.version}, в шорт-листе {n.shortlist_count}</span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>

          {current && (
            <section aria-label={current.title} className="min-w-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-xl font-bold text-ink">{current.title}</h2>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5 text-sm text-ink-2">
                    <span>{current.params.role ? ROLE_RU[current.params.role] : 'любая специализация'}, {current.params.grade ? gradeRu(current.params.grade) : 'любой грейд'}</span>
                    {current.params.skills.map(s => <span key={s} className="chip-active">{s}</span>)}
                    {current.params.nice_to_have.map(s => <span key={s} className="chip-default">+ {s}</span>)}
                    {current.params.work_goal === 'internship' && <span className="badge-warn">стажировка</span>}
                  </div>
                </div>
                <button onClick={() => edit(current)} className="btn-secondary btn-sm"><Pencil size={14} aria-hidden />Изменить</button>
              </div>

              {matches.data?.recommended_categories?.length > 0 && (
                <div className="panel-quiet mt-5 text-sm">
                  <p className="text-ink-2">Где искать: самые сильные совпадения в категориях</p>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {matches.data.recommended_categories.map((c: { role: string; grade: string; candidates: number; best: number }) => (
                      <li key={`${c.role}-${c.grade}`} className="rounded-md bg-panel px-3 py-1.5 ring-1 ring-line">
                        <span className="font-medium text-ink">{ROLE_RU[c.role] ?? c.role} {c.grade}</span>
                        <span className="text-ink-3"> — {c.candidates} канд., лучшее {Math.round(c.best * 100)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-6 flex gap-6 border-b border-line" role="tablist">
                {([['matches', 'Подборка'], ['shortlist', `Шорт-лист ${shortItems.length}`], ['exam', 'Как проверим']] as const).map(([key, title]) => (
                  <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`-mb-px border-b-2 pb-3 text-sm ${tab === key ? 'border-accent font-semibold text-ink' : 'border-transparent text-ink-2 hover:text-ink'}`}>{title}</button>
                ))}
              </div>
              {sent && <p className="notice-ok mt-4" role="status">Приглашение отправлено.</p>}

              {tab === 'matches' && (
                <div className="mt-5 space-y-4">
                  {picked.length > 0 && (
                    <div className="card">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm text-ink-2">В сравнении {picked.length} из 3{picked.length < 2 ? ': отметьте ещё одного кандидата' : ''}. Имя и контакты в сравнение не попадают.</p>
                        <button type="button" onClick={() => setPicked([])} className="text-xs text-accent hover:underline">Очистить</button>
                      </div>
                      {compared.data && compared.data.items.length >= 2 && (
                        <div className="mt-3 overflow-x-auto">
                          <table className="protocol">
                            <thead><tr><th>Фактор</th>{compared.data.items.map(c => <th key={c.candidate_id}>{ROLE_RU[c.role] ?? c.role} {c.grade}</th>)}</tr></thead>
                            <tbody>
                              <tr><td>Совпадение</td>{compared.data.items.map(c => <td key={c.candidate_id} className="num">{Math.round((c.score ?? 0) * 100)}</td>)}</tr>
                              {(compared.data.items[0]?.factors ?? []).map(f => {
                                const values = compared.data!.items.map(c => c.factors.find(x => x.key === f.key)?.value ?? null)
                                const known = values.filter((v): v is number => v != null)
                                const best = known.length > 1 && new Set(known).size > 1 ? Math.max(...known) : null
                                return (
                                  <tr key={f.key}><td>{f.label}</td>{values.map((v, i) => (
                                    <td key={compared.data!.items[i].candidate_id} className={`num ${v != null && v === best ? 'font-semibold text-accent' : ''}`}>
                                      {v == null ? '—' : Math.round(v * 100)}
                                    </td>
                                  ))}</tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                  {matches.isLoading && <><Skeleton className="h-48" /><Skeleton className="h-48" /></>}
                  {matches.data && (matches.data.items ?? []).length === 0 && <Empty title="Совпадений нет">Уберите часть обязательных навыков или грейд.</Empty>}
                  {(matches.data?.items ?? []).map((card: CandidateCardData, i: number) => (
                    <CandidateCard key={card.candidate_id} card={card} place={i + 1} onOffer={setOfferFor} onTask={setTaskFor}
                      onShortlist={(id, on) => toggle.mutate({ id, on })}
                      compare={{
                        on: picked.includes(card.candidate_id), full: picked.length >= 3,
                        toggle: () => setPicked(prev => prev.includes(card.candidate_id) ? prev.filter(x => x !== card.candidate_id) : prev.length >= 3 ? prev : [...prev, card.candidate_id]),
                      }} />
                  ))}
                </div>
              )}
              {tab === 'exam' && (
                <div className="card mt-5">
                  <p className="mb-4 text-sm text-ink-2">Кандидат, которого вы пригласите, подтверждает грейд этим тестом. Состав считается из навыков и текста потребности; задания каждый раз генерируются заново.</p>
                  {exam.isLoading && <Skeleton className="h-40" />}
                  {exam.data && <ExamPreview exam={exam.data} />}
                </div>
              )}

              {tab === 'shortlist' && (
                <div className="mt-5">
                  {shortlist.data && (
                    <p className="mb-4 text-sm text-ink-2">Отобрано {shortlist.data.funnel.shortlisted}, приглашено {shortlist.data.funnel.invited}, отказ {shortlist.data.funnel.rejected}.</p>
                  )}
                  {shortItems.length === 0 ? <Empty title="Шорт-лист пуст">Отмечайте кандидатов звёздочкой в подборке.</Empty> : (
                    <div className="card overflow-x-auto p-0">
                      <table className="protocol">
                        <thead><tr><th>Категория</th><th className="text-right">Совпадение</th><th>Выбран по версии</th><th>Добавлен</th><th /></tr></thead>
                        <tbody>
                          {shortItems.map((r: { candidate_id: string; role: string; grade: string; score: number; picked_on_version: number; added_at: string }) => (
                            <tr key={r.candidate_id}>
                              <td className="text-ink">{ROLE_RU[r.role] ?? r.role} {r.grade}</td>
                              <td className="num text-right font-semibold text-ink">{Math.round((r.score ?? 0) * 100)}</td>
                              <td className="text-ink-2">v{r.picked_on_version}{r.picked_on_version !== current.version && ' (до изменения)'}</td>
                              <td className="num text-ink-2">{date(r.added_at)}</td>
                              <td className="text-right"><button onClick={() => setOfferFor(r.candidate_id)} className="btn-invite-quiet btn-sm">Пригласить</button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </section>
          )}
        </div>
      )}
      {taskFor && <TaskDialog candidateId={taskFor} onClose={() => setTaskFor(null)} />}
      {offerFor && <InviteDialog candidateId={offerFor} defaultRole={current?.title ?? ''} onClose={() => setOfferFor(null)} onSent={() => setSent(true)} />}
    </div>
  )
}
