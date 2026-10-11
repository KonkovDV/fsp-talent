import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import {
  apiError, compareNeed, needExam, createNeed, draftNeed, draftNeedFromUrl, getNeed, hideCandidate, listNeeds, needMatches, needShortlist, removeShortlist, restoreNeed, setShortlist, surveyOptions, unhideCandidate, updateNeed,
} from '../../api/client'
import { NEED_EXAMPLES } from '../../needExamples'
import CandidateCard, { type CandidateCardData } from '../../components/CandidateCard'
import { useFavorites } from '../../hooks/useFavorites'
import InviteDialog from '../../components/InviteDialog'
import TaskDialog from '../../components/TaskDialog'
import ExamPreview, { type Exam } from '../../components/ExamPreview'
import { CategoryPlate, Empty, PageHeader, Skeleton, date, rub } from '../../components/ui'
import { netLine } from '../../money'
import { ROLE_RU, gradeRu } from '../../labels'

interface NeedParams {
  role: string | null; grade: string | null; grade_match?: 'exact' | 'plus_minus' | 'any'; skills: string[]; nice_to_have: string[]
  industry: string | null; work_goal: string | null; has_fsp: boolean | null
  salary_from?: number | null; salary_to?: number | null
  city?: string | null; work_format?: string | null
}
interface PayHint { known: number; covered: number; proposed_to: number; covered_if_raised: number; gained: number }
interface SkillHint { skill: string; gained: number; pool: number }
interface Need { id: string; title: string; version: number; params: NeedParams; shortlist_count: number; flags?: { code: string; label: string }[] }

const EMPTY = { title: '', role: '', grade: '', gradeMatch: 'plus_minus', skills: '', nice: '', industry: '', internship: false, payFrom: '', payTo: '', city: '', format: '', paste: '', pageUrl: '' }
const PRESETS = [
  { label: 'Высокая нагрузка', title: 'Сервис под нагрузкой', role: 'backend', grade: 'senior', skills: 'Go, PostgreSQL, Kafka', format: 'remote' },
  { label: 'Искусственный интеллект', title: 'Модели в продукте', role: 'ml', grade: 'middle', skills: 'Python, PyTorch', format: 'hybrid' },
  { label: 'Робототехника', title: 'Бортовое ПО', role: 'embedded', grade: 'middle', skills: 'C++, ROS', format: 'office' },
]
const money = (raw: string) => { const n = Number(raw); return raw.trim() && Number.isFinite(n) ? n : null }
const csv = (s: string) => s.split(',').map(x => x.trim()).filter(Boolean)

/** Employer needs: what we look for (versioned), explainable matches, recommended categories, shortlist. */
export default function EmployerNeeds() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string | null>(null)
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const [error, setError] = useState('')
  const [draftNotes, setDraftNotes] = useState<string[]>([])
  const [offerFor, setOfferFor] = useState<string | null>(null)
  const [taskFor, setTaskFor] = useState<string | null>(null)
  const [tab, setTab] = useState<'matches' | 'shortlist' | 'exam'>('matches')
  const [shortStatus, setShortStatus] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [showHidden, setShowHidden] = useState(false)
  const [sent, setSent] = useState(false)

  const { data: opts } = useQuery({ queryKey: ['surveyOptions'], queryFn: () => surveyOptions().then(r => r.data) })
  const { data: needs = [], isLoading: needsLoading, isError: needsError, error: needsLoadError } = useQuery<Need[]>({ queryKey: ['needs'], queryFn: () => listNeeds().then(r => r.data) })
  useEffect(() => { if (!selected && needs.length) setSelected(needs[0].id) }, [needs, selected])
  useEffect(() => { setPicked([]); setSent(false); setShowHidden(false); setShortStatus('') }, [selected])
  const current = needs.find(n => n.id === selected) ?? null
  const matches = useQuery({ queryKey: ['needMatches', selected, current?.version, showHidden], enabled: !!selected,
    queryFn: () => needMatches(selected!, showHidden).then(r => r.data) })
  const compared = useQuery({
    queryKey: ['needCompare', selected, picked.join(',')],
    enabled: !!selected && picked.length >= 2,
    queryFn: () => compareNeed(selected!, picked).then(r => r.data as { items: { candidate_id: string; role: string; grade: string; score: number; factors: { key: string; label: string; value: number | null }[] }[] }),
  })
  const exam = useQuery({ queryKey: ['needExam', selected, current?.version], enabled: !!selected && tab === 'exam',
    queryFn: () => needExam(selected!).then(r => r.data as Exam) })
  const shortlist = useQuery({ queryKey: ['needShortlist', selected, shortStatus], enabled: !!selected,
    queryFn: () => needShortlist(selected!, shortStatus || undefined).then(r => r.data) })

  const detail = useQuery({ queryKey: ['need', selected], enabled: !!selected,
    queryFn: () => getNeed(selected!).then(r => r.data as Need & { versions: { version: number; params: NeedParams }[] }) })
  const body = () => ({
    title: form.title.trim(),
    params: { role: form.role || null, grade: form.grade || null, grade_match: form.gradeMatch, skills: csv(form.skills), nice_to_have: csv(form.nice),
      industry: form.industry || null, work_goal: form.internship ? 'internship' : null,
      salary_from: money(form.payFrom), salary_to: money(form.payTo),
      city: form.city || null, work_format: form.format || null },
    ...(editing && editing !== 'new' && current ? { expected_version: current.version } : {}),
  })
  const save = useMutation({
    mutationFn: () => (editing === 'new' ? createNeed(body()) : updateNeed(editing!, body())).then(r => r.data),
    onSuccess: (need: Need) => {
      setEditing(null); setSelected(need.id); setError('')
      qc.invalidateQueries({ queryKey: ['needs'] })
      qc.invalidateQueries({ queryKey: ['need', need.id] })
    },
    onError: (e: unknown) => setError(apiError(e)),
  })
  const parsed = useMutation({
    mutationFn: (url?: string) => (url ? draftNeedFromUrl(url) : draftNeed(form.paste)).then(r => r.data as {
      title: string; role: string | null; grade: string | null; skills: string[]; nice_to_have: string[]
      salary_from: number | null; salary_to: number | null; work_format: string | null; city: string | null
      industry: string | null; work_goal: string | null; notes: string[]; flags?: { code: string; label: string }[]
    }),
    onSuccess: (d) => {
      setError('')
      setDraftNotes(d.notes ?? [])
      setForm(f => ({
        ...f,
        title: d.title || f.title,
        role: d.role ?? '',
        grade: d.grade ?? '',
        skills: (d.skills ?? []).join(', '),
        nice: (d.nice_to_have ?? []).join(', '),
        industry: d.industry ?? '',
        internship: d.work_goal === 'internship',
        payFrom: d.salary_from != null ? String(d.salary_from) : '',
        payTo: d.salary_to != null ? String(d.salary_to) : '',
        city: d.city ?? '',
        format: d.work_format ?? '',
      }))
    },
    onError: (e: unknown) => setError(apiError(e, 'Текст не разобран')),
  })
  const fav = useFavorites()
  const hide = useMutation({
    mutationFn: (card: CandidateCardData) => card.hidden ? unhideCandidate(selected!, card.candidate_id) : hideCandidate(selected!, card.candidate_id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['needMatches'] }),
  })
  const toggle = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => on ? setShortlist(selected!, id) : removeShortlist(selected!, id),
    onSuccess: () => {
      setError('')
      for (const k of ['needMatches', 'needShortlist', 'needs']) qc.invalidateQueries({ queryKey: [k] })
    },
    onError: (e: unknown) => setError(apiError(e, 'Шорт-лист не изменился')),
  })
  const restore = useMutation({
    mutationFn: (version: number) => restoreNeed(selected!, version).then(r => r.data),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['needs'] })
      qc.invalidateQueries({ queryKey: ['need', selected] })
    },
    onError: (e: unknown) => setError(apiError(e, 'Не удалось вернуть версию')),
  })
  const edit = (n: Need) => {
    setEditing(n.id)
    setForm({ title: n.title, role: n.params.role ?? '', grade: n.params.grade ?? '',
      gradeMatch: n.params.grade_match ?? 'plus_minus', skills: n.params.skills.join(', '),
      nice: n.params.nice_to_have.join(', '), industry: n.params.industry ?? '', internship: n.params.work_goal === 'internship',
      payFrom: n.params.salary_from != null ? String(n.params.salary_from) : '',
      payTo: n.params.salary_to != null ? String(n.params.salary_to) : '',
      city: n.params.city ?? '', format: n.params.work_format ?? '', paste: '', pageUrl: '' })
  }
  const field = 'field-label'
  const shortItems = shortlist.data?.items ?? []
  const funnel = shortlist.data?.funnel as { shortlisted: number; invited: number; rejected: number } | undefined
  const shortCount = funnel ? funnel.shortlisted + funnel.invited + funnel.rejected : shortItems.length

  return (
    <div>
      <PageHeader title="Потребности"
        lead="Опишите, кого ищете. Каждое изменение сохраняется новой версией, а шорт-лист помнит, по какой версии выбран кандидат."
        actions={<button onClick={() => { setEditing('new'); setForm(EMPTY); setDraftNotes([]) }} className="btn-primary"><Plus size={16} aria-hidden />Новая потребность</button>} />

      {editing && (
        <form className="card mb-8 space-y-5" onSubmit={e => { e.preventDefault(); save.mutate() }} aria-label="Потребность">
          <h2 className="section-title">{editing === 'new' ? 'Новая потребность' : 'Изменение — будет сохранено новой версией'}</h2>
          <div>
            <label className={field} htmlFor="n-paste">Текст вакансии</label>
            <textarea id="n-paste" value={form.paste} onChange={e => setForm({ ...form, paste: e.target.value })} rows={4}
              placeholder="Вставьте текст. Сайт вакансий не открывается: разбираются только эти строки." className="input" aria-label="Текст вакансии" />
            <div className="mt-2 flex flex-wrap items-center gap-2" aria-label="Примеры потребности">
              <span className="text-xs text-ink-3">Пример:</span>
              {NEED_EXAMPLES.map(ex => (
                <button key={ex.label} type="button" className="chip-default hover:border-accent" onClick={() => setForm({ ...form, paste: ex.text })}>{ex.label}</button>
              ))}
            </div>
            <button type="button" className="btn-secondary btn-sm mt-2" disabled={form.paste.trim().length < 10 || parsed.isPending} onClick={() => parsed.mutate(undefined)}>Разобрать текст</button>
            <label className={field} htmlFor="n-url">Или одна открытая ссылка</label>
            <input id="n-url" value={form.pageUrl} onChange={e => setForm({ ...form, pageUrl: e.target.value })} placeholder="https://…" className="input" aria-label="Ссылка на страницу вакансии" />
            <button type="button" className="btn-secondary btn-sm mt-2" disabled={!(form.pageUrl ?? '').startsWith('http') || parsed.isPending} onClick={() => parsed.mutate(form.pageUrl)}>Разобрать страницу</button>
            <p className="field-hint">Берётся только эта страница. Переход по ссылке внутри неё не выполняется. Внутренний адрес отклоняется.</p>
            {draftNotes.length > 0 && <ul className="mt-2 text-sm text-ink-2">{draftNotes.map(line => <li key={line}>{line}</li>)}</ul>}
            {(parsed.data?.flags ?? []).length > 0 && <p className="mt-2 text-sm text-warn">В тексте: {parsed.data!.flags!.map(flag => flag.label.toLowerCase()).join('; ')}. Потребность всё равно можно сохранить.</p>}
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Готовые потребности">
            {PRESETS.map(preset => (
              <button type="button" key={preset.label} className="chip-default" onClick={() => setForm(current => ({
                ...current, title: preset.title, role: preset.role, grade: preset.grade, skills: preset.skills, format: preset.format,
              }))}>{preset.label}</button>
            ))}
          </div>
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
            <div><label className={field} htmlFor="n-match">Как сравнивать грейд</label>
              <select id="n-match" value={form.gradeMatch} onChange={e => setForm({ ...form, gradeMatch: e.target.value })} className="select" aria-label="Как сравнивать грейд">
                <option value="plus_minus">Плюс-минус один шаг</option>
                <option value="exact">Только этот грейд</option>
                <option value="any">Любой грейд</option>
              </select></div>
            <div><label className={field} htmlFor="n-ind">Предметная область (необязательно)</label>
              <select id="n-ind" value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} className="select" aria-label="Предметная область">
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
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className={field} htmlFor="n-from">Вилка от, до вычета НДФЛ</label>
              <input id="n-from" inputMode="numeric" value={form.payFrom} onChange={e => setForm({ ...form, payFrom: e.target.value })} placeholder="180000" className="input num" aria-label="Вилка от" /></div>
            <div><label className={field} htmlFor="n-to">Вилка до, до вычета НДФЛ</label>
              <input id="n-to" inputMode="numeric" value={form.payTo} onChange={e => setForm({ ...form, payTo: e.target.value })} placeholder="260000" className="input num" aria-label="Вилка до" />
              <p className="field-hint">Если кандидат указал ожидание, место в подборке учитывает, примет ли он такую вилку. {netLine(Number(form.payFrom) || null, Number(form.payTo) || null)}</p></div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className={field} htmlFor="n-city">Город</label>
              <select id="n-city" value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} className="select" aria-label="Город">
                <option value="">Не важен</option>
                {(opts?.cities ?? []).map((name: string) => <option key={name} value={name}>{name}</option>)}
              </select></div>
            <div><label className={field} htmlFor="n-fmt">Формат</label>
              <select id="n-fmt" value={form.format} onChange={e => setForm({ ...form, format: e.target.value })} className="select" aria-label="Формат">
                <option value="">Не важен</option>
                {Object.entries(opts?.work_formats ?? {}).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
              </select></div>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink"><input type="checkbox" checked={form.internship} onChange={e => setForm({ ...form, internship: e.target.checked })} />Ищем стажёра или практиканта</label>
          {error && <p className="notice-error" role="alert">{error}</p>}
          <div className="flex gap-3">
            <button className="btn-primary" disabled={form.title.trim().length < 2 || save.isPending}>{editing === 'new' ? 'Создать' : 'Сохранить новую версию'}</button>
            <button type="button" className="btn-secondary" onClick={() => setEditing(null)}>Отмена</button>
          </div>
        </form>
      )}

      {needsError && <p className="notice-error mb-4" role="alert">{apiError(needsLoadError, 'Не удалось загрузить потребности')}</p>}
      {!needsLoading && !needsError && needs.length === 0 && !editing && (
        <Empty title="Потребностей пока нет" action={<button onClick={() => { setEditing('new'); setForm(EMPTY); setDraftNotes([]) }} className="btn-primary">Создать первую</button>}>
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
                    className={`relative w-full rounded-lg px-3.5 py-2.5 text-left transition-colors ${n.id === selected ? 'bg-panel shadow-xs ring-1 ring-line-strong before:absolute before:inset-y-2.5 before:left-0 before:w-[3px] before:rounded-full before:bg-accent' : 'hover:bg-panel/70'}`}>
                    <span className="block text-sm font-medium text-ink">{n.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-3">версия {n.version}, в шорт-листе {n.shortlist_count}</span>
                    {(n.flags ?? []).length > 0 && <span className="mt-1 block text-xs text-warn">{n.flags!.map(flag => flag.label).join('; ')}</span>}
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
                    {(current.params.salary_from != null || current.params.salary_to != null) && (
                      <span className="num">{rub(current.params.salary_from)} – {rub(current.params.salary_to)}</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => edit(current)} className="btn-secondary btn-sm"><Pencil size={14} aria-hidden />Изменить</button>
                </div>
              </div>

              {(detail.data?.versions?.length ?? 0) > 1 && (
                <ul className="mt-3 flex flex-wrap gap-2 text-xs text-ink-2">
                  {detail.data!.versions.filter((v: { version: number }) => v.version !== current.version).map((v: { version: number }) => (
                    <li key={v.version}>
                      <button type="button" className="chip-default" disabled={restore.isPending} onClick={() => restore.mutate(v.version)}>
                        Вернуть версию {v.version}
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {matches.data?.recommended_categories?.length > 0 && (
                <div className="panel-quiet mt-5 text-sm">
                  <p className="text-ink-2">Где искать: самые сильные совпадения в категориях. Ссылка открывает поиск с фильтрами.</p>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {matches.data.recommended_categories.map((c: { role: string; grade: string; candidates: number; best: number }) => (
                      <li key={`${c.role}-${c.grade}`}>
                        <Link to={`/employer/search?role=${c.role}&grade=${c.grade}`} className="inline-flex min-h-9 items-center gap-1 rounded-md bg-panel px-3 py-1.5 shadow-xs ring-1 ring-line-strong/70 transition-shadow hover:ring-accent">
                          <span className="font-medium text-accent">{ROLE_RU[c.role] ?? c.role}, {gradeRu(c.grade)}</span>
                          <span className="text-ink-3"> — {c.candidates} канд., лучшее совпадение {Math.round(c.best * 100)}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="tabs mt-6" role="tablist" aria-label="Разделы потребности">
                {([['matches', 'Подборка'], ['shortlist', `Шорт-лист ${shortCount}`], ['exam', 'Как проверим']] as const).map(([key, title]) => (
                  <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className="tab">{title}</button>
                ))}
              </div>
              {sent && <p className="notice-ok mt-4" role="status">Приглашение отправлено.</p>}
              {error && !editing && <p className="notice-error mt-4" role="alert">{error}</p>}

              {tab === 'matches' && (
                <div className="mt-5 space-y-4">
                  <p className="text-sm text-ink-3">Балл расставляет карточки и никого из них не выбрасывает. Приглашение отправляет человек.</p>
                  {matches.data?.base_total != null && (
                    <p className="text-sm text-ink-2">По условиям этой потребности {matches.data.total ?? 0} из {matches.data.base_total} в банке.{(matches.data.platform_held ?? 0) > 0 ? ` Площадка не показала ${matches.data.platform_held}. Уровень компании здесь не пишется.` : ''}</p>
                  )}
                  {matches.data?.pay_hint?.gained > 0 && (
                    <p className="text-sm text-ink-2">
                      Если поднять верх вилки до <span className="num">{rub((matches.data.pay_hint as PayHint).proposed_to)}</span>,
                      ожидание закроется ещё у {(matches.data.pay_hint as PayHint).gained} из {(matches.data.pay_hint as PayHint).known} кандидатов, которые его указали.
                    </p>
                  )}
                  {matches.data?.skill_hint?.gained > 0 && (
                    <p className="text-sm text-ink-2">
                      Если не требовать «{(matches.data.skill_hint as SkillHint).skill}», ещё {(matches.data.skill_hint as SkillHint).gained} кандидатов закроют все остальные обязательные навыки.
                    </p>
                  )}
                  {picked.length > 0 && (
                    <div className="card">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm text-ink-2">В сравнении {picked.length} из 4{picked.length < 2 ? ': отметьте ещё одного кандидата' : ''}. Имя и контакты в сравнение не попадают.</p>
                        <button type="button" onClick={() => setPicked([])} className="btn-ghost btn-sm text-accent">Очистить</button>
                      </div>
                      {compared.data && compared.data.items.length >= 2 && (
                        <div className="mt-3 overflow-x-auto" tabIndex={0} role="region" aria-label="Сравнение кандидатов">
                          <table className="protocol">
                            <thead><tr><th>Фактор</th>{compared.data.items.map(c => <th key={c.candidate_id}>{ROLE_RU[c.role] ?? c.role}, {gradeRu(c.grade)}</th>)}</tr></thead>
                            <tbody>
                              <tr><td className="font-medium text-ink">Совпадение</td>{compared.data.items.map(c => <td key={c.candidate_id} className="num font-display text-lg font-bold text-ink">{Math.round((c.score ?? 0) * 100)}</td>)}</tr>
                              {(compared.data.items[0]?.factors ?? []).map(f => {
                                const values = compared.data!.items.map(c => c.factors.find(x => x.key === f.key)?.value ?? null)
                                const known = values.filter((v): v is number => v != null)
                                const best = known.length > 1 && new Set(known).size > 1 ? Math.max(...known) : null
                                return (
                                  <tr key={f.key}><td>{f.label}</td>{values.map((v, i) => (
                                    <td key={compared.data!.items[i].candidate_id} className={`num min-w-[7rem] ${v != null && v === best ? 'font-semibold text-accent' : 'text-ink-2'}`}>
                                      {v == null ? <span className="text-ink-3">не учитывается</span> : (
                                        <span className="flex items-center gap-2">
                                          <span className="w-7 shrink-0 text-right">{Math.round(v * 100)}</span>
                                          <span className="meter w-full max-w-[6rem]" aria-hidden><span style={{ width: `${Math.round(v * 100)}%` }} className={v === best ? '' : '!bg-ink-3'} /></span>
                                        </span>
                                      )}
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
                  {matches.isError && <p className="notice-error" role="alert">{apiError(matches.error, 'Подборка не загрузилась')}</p>}
                  {matches.data && !matches.isError && (matches.data.items ?? []).length === 0 && <Empty title="Совпадений нет">Уберите часть обязательных навыков или грейд.</Empty>}
                  {(matches.data?.hidden_count ?? 0) > 0 && (
                    <button type="button" className="btn-ghost text-sm" onClick={() => setShowHidden(v => !v)}>
                      {showHidden ? 'Скрыть убранных' : `Показать скрытых (${matches.data.hidden_count})`}
                    </button>
                  )}
                  {matches.data && (matches.data.total ?? 0) > (matches.data.items ?? []).length && (
                    <p className="text-sm text-ink-2">На экране первые {(matches.data.items ?? []).length} из {matches.data.total}.</p>
                  )}
                  {(matches.data?.items ?? []).map((card: CandidateCardData, i: number) => (
                    <CandidateCard key={card.candidate_id} card={card} place={i + 1} onOffer={setOfferFor} onTask={setTaskFor}
                      aiNote={matches.data?.ai_note ? { needId: selected! } : undefined}
                      onShortlist={(id, on) => toggle.mutate({ id, on })}
                      onHide={() => hide.mutate(card)}
                      favorite={{ on: fav.has(card.candidate_id), toggle: fav.toggle }}
                      compare={{
                        on: picked.includes(card.candidate_id), full: picked.length >= 4,
                        toggle: () => setPicked(prev => prev.includes(card.candidate_id) ? prev.filter(x => x !== card.candidate_id) : prev.length >= 4 ? prev : [...prev, card.candidate_id]),
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
                  {funnel && (
                    <p className="mb-4 text-sm text-ink-2">Отобрано {funnel.shortlisted}, приглашено {funnel.invited}, отказ {funnel.rejected}.</p>
                  )}
                  <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Шаг воронки">
                    {([
                      ['', 'Все'],
                      ['shortlisted', 'Отобрано'],
                      ['invited', 'Приглашено'],
                      ['rejected', 'Отказ'],
                    ] as const).map(([value, label]) => (
                      <button type="button" key={label} aria-pressed={shortStatus === value} onClick={() => setShortStatus(value)}
                        className={shortStatus === value ? 'chip-active' : 'chip-default'}>
                        {label}{value && funnel ? ` ${funnel[value]}` : ''}
                      </button>
                    ))}
                  </div>
                  {shortItems.length === 0 ? <Empty title={shortStatus ? 'На этом шаге никого' : 'Шорт-лист пуст'}>{shortStatus ? 'Выберите другой шаг воронки.' : 'Отмечайте кандидатов звёздочкой в подборке.'}</Empty> : (
                    <>
                    <ul className="space-y-3 sm:hidden">
                      {shortItems.map((r: { candidate_id: string; role: string; grade: string; grade_source?: string | null; also_primary?: { role: string | null; grade: string | null; grade_source: string | null } | null; score: number; picked_on_version: number; added_at: string }) => (
                        <li key={r.candidate_id} className="card space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <CategoryPlate role={r.role} grade={r.grade} source={r.grade_source} />
                            <span className="num text-lg font-semibold text-ink">{Math.round((r.score ?? 0) * 100)}</span>
                          </div>
                          {r.also_primary?.role && <p className="text-xs text-ink-3">Основная категория: {ROLE_RU[r.also_primary.role] ?? r.also_primary.role}{r.also_primary.grade ? `, ${gradeRu(r.also_primary.grade)}` : ''}</p>}
                          <p className="text-sm text-ink-2">Выбран по версии {r.picked_on_version}{r.picked_on_version !== current.version && ' (до изменения)'}</p>
                          <p className="text-sm text-ink-2">Добавлен {date(r.added_at)}</p>
                          <button onClick={() => setOfferFor(r.candidate_id)} className="btn-invite-quiet btn-sm">Пригласить</button>
                        </li>
                      ))}
                    </ul>
                    <div className="card hidden overflow-x-auto p-0 sm:block" tabIndex={0} role="region" aria-label="Шорт-лист">
                      <table className="protocol">
                        <thead><tr><th>Категория</th><th className="text-right">Совпадение</th><th>Выбран по версии</th><th>Добавлен</th><th /></tr></thead>
                        <tbody>
                          {shortItems.map((r: { candidate_id: string; role: string; grade: string; grade_source?: string | null; also_primary?: { role: string | null; grade: string | null } | null; score: number; picked_on_version: number; added_at: string }) => (
                            <tr key={r.candidate_id}>
                              <td>
                                <CategoryPlate role={r.role} grade={r.grade} source={r.grade_source} />
                                {r.also_primary?.role && <p className="mt-1 text-xs text-ink-3">Основная категория: {ROLE_RU[r.also_primary.role] ?? r.also_primary.role}{r.also_primary.grade ? `, ${gradeRu(r.also_primary.grade)}` : ''}</p>}
                              </td>
                              <td className="num text-right font-semibold text-ink">{Math.round((r.score ?? 0) * 100)}</td>
                              <td className="text-ink-2">версия {r.picked_on_version}{r.picked_on_version !== current.version && ' (до изменения)'}</td>
                              <td className="num text-ink-2">{date(r.added_at)}</td>
                              <td className="text-right"><button onClick={() => setOfferFor(r.candidate_id)} className="btn-invite-quiet btn-sm">Пригласить</button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    </>
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
