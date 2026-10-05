import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { apiError, createOffer, parseQuery, searchCandidates } from '../../api/client'
import { DISC_RU, ROLE_RU } from '../../labels'
import { Search, X, SlidersHorizontal } from 'lucide-react'
import CandidateCard, { type CandidateCardData } from '../../components/CandidateCard'

const ROLES  = ['', 'backend', 'frontend', 'fullstack', 'ml', 'devops', 'security', 'embedded', 'mobile']
const GRADES = ['', 'junior', 'middle', 'senior', 'lead']
const DISCS  = ['', 'algorithmic', 'product', 'security', 'bas', 'robotics']
const RANKS  = ['', 'МС', 'КМС', 'I', 'II', 'III']

function Tag({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="chip chip-active">
      {label}
      <button onClick={onRemove} className="ml-0.5 opacity-70 hover:opacity-100" aria-label={`Удалить ${label}`}>
        <X size={11}/>
      </button>
    </span>
  )
}

export default function EmployerSearch() {
  const [q,           setQ]          = useState('')
  const [role,        setRole]       = useState('')
  const [grade,       setGrade]      = useState('')
  const [discipline,  setDiscipline] = useState('')
  const [minRank,     setMinRank]    = useState('')
  const [skills,      setSkills]     = useState('')
  const [assessedOnly, setAssessedOnly] = useState(false)
  const [hasFsp, setHasFsp] = useState('')
  const [internship, setInternship] = useState(false)
  const [offerFor,    setOfferFor]   = useState<string | null>(null)
  const [filtersOpen, setFiltersOpen]= useState(true)

  const params = {
    q:          q          || undefined,
    role:       role       || undefined,
    grade:      grade      || undefined,
    discipline: discipline || undefined,
    min_rank:   minRank    || undefined,
    skills:     skills     || undefined,
    assessed_only: assessedOnly || undefined,
    has_fsp:    hasFsp || undefined,
    work_goal:  internship ? 'internship' : undefined,
  }

  // Filters edit a draft. The shown selection changes only on "Найти" and stays on screen while the
  // refined query loads (TZ: "уточнение запроса без потери ранее полученной подборки").
  const [submitted, setSubmitted] = useState<typeof params | null>(null)
  const { data, isFetching } = useQuery({
    queryKey: ['search', submitted],
    queryFn:  () => searchCandidates(submitted!).then(r => r.data),
    enabled:  submitted !== null,
    placeholderData: keepPreviousData,
  })
  const draftChanged = submitted !== null && JSON.stringify(submitted) !== JSON.stringify(params)

  const parsed = useMutation({
    mutationFn: () => parseQuery(q).then(r => r.data),
    onSuccess: (res) => {
      if (res.role)           setRole(res.role)
      if (res.grade)          setGrade(res.grade)
      if (res.discipline)     setDiscipline(res.discipline)
      if (res.skills?.length) setSkills(res.skills.join(', '))
    },
  })

  const doSearch = () => setSubmitted({ ...params })

  const activeTags = [
    role       && { label: ROLE_RU[role]          ?? role,       clear: () => { setRole('') } },
    grade      && { label: grade,                                clear: () => { setGrade('') } },
    discipline && { label: DISC_RU[discipline]     ?? discipline, clear: () => { setDiscipline('') } },
    minRank    && { label: `разряд от ${minRank}`,               clear: () => { setMinRank('') } },
  ].filter(Boolean) as { label: string; clear: () => void }[]

  // Normalise: add mu from lcb when mu is missing
  const cards: CandidateCardData[] = (data?.items ?? []).map((c: any) => ({
    ...c,
    disciplines: (c.disciplines ?? []).map((d: any) => ({
      ...d,
      mu:  d.score ?? d.mu ?? d.lcb ?? 0,
      lcb: d.lcb ?? 0,
    })),
  }))

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Поиск кандидатов</h1>
        <p className="text-sm text-text-muted mt-1">
          Карточки анонимны. Имя и контакты открываются только после согласия кандидата.
        </p>
      </div>

      {/* Command bar */}
      <div className="card space-y-3">
        <div className="flex gap-2 flex-wrap">
          <div className="flex-1 min-w-60 relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden />
            <input
              value={q}
              onChange={e => { setQ(e.target.value) }}
              onKeyDown={e => e.key === 'Enter' && doSearch()}
              placeholder="сеньор бэкенд, Python, чемпионат…"
              className="input pl-10"
              aria-label="Поиск"
            />
          </div>

          {activeTags.map(t => <Tag key={t.label} label={t.label} onRemove={t.clear} />)}

          <button
            onClick={() => setFiltersOpen(o => !o)}
            className="btn-ghost gap-1.5 text-xs"
            aria-expanded={filtersOpen}
          >
            <SlidersHorizontal size={14}/> Фильтры
          </button>
          <button
            onClick={() => parsed.mutate()}
            disabled={!q || parsed.isPending}
            className="btn-secondary text-xs"
          >
            Разобрать AI
          </button>
          <button onClick={doSearch} className="btn-primary text-xs">
            {isFetching ? 'Ищём…' : 'Найти'}
          </button>
        </div>

        {filtersOpen && (
          <div className="flex gap-2 flex-wrap pt-2 border-t border-border">
            <select value={role}       onChange={e => { setRole(e.target.value) }} className="select text-xs w-auto">
              {ROLES.map(v  => <option key={v} value={v}>{v ? ROLE_RU[v] : 'Любая роль'}</option>)}
            </select>
            <select value={grade}      onChange={e => { setGrade(e.target.value) }} className="select text-xs w-auto">
              {GRADES.map(v => <option key={v} value={v}>{v || 'Любой грейд'}</option>)}
            </select>
            <select value={discipline} onChange={e => { setDiscipline(e.target.value) }} className="select text-xs w-auto">
              {DISCS.map(v  => <option key={v} value={v}>{v ? DISC_RU[v] : 'Любая дисциплина'}</option>)}
            </select>
            <select value={minRank}    onChange={e => { setMinRank(e.target.value) }} className="select text-xs w-auto">
              {RANKS.map(v  => <option key={v} value={v}>{v ? `разряд от ${v}` : 'Любой разряд'}</option>)}
            </select>
            <input
              value={skills}
              onChange={e => { setSkills(e.target.value) }}
              placeholder="Навыки через запятую"
              className="input text-xs min-w-48 w-auto flex-1"
            />
            <label className="flex items-center gap-1.5 text-xs text-text-secondary">
              <input type="checkbox" checked={assessedOnly}
                onChange={e => { setAssessedOnly(e.target.checked) }} />
              Только грейд, подтверждённый тестом
            </label>
            <select value={hasFsp} onChange={e => setHasFsp(e.target.value)} className="input text-xs w-auto" aria-label="История ФСП">
              <option value="">ФСП: все</option>
              <option value="true">С историей ФСП</option>
              <option value="false">Без истории ФСП</option>
            </select>
            <label className="flex items-center gap-1.5 text-xs text-text-secondary">
              <input type="checkbox" checked={internship} onChange={e => setInternship(e.target.checked)} />
              Стажировка / практика
            </label>
          </div>
        )}
      </div>

      {draftChanged && (
        <p className="text-xs text-text-muted" role="status">
          Фильтры изменены. Ниже прежняя подборка, нажмите «Найти», чтобы обновить.
        </p>
      )}

      {submitted && data && (
        <p className="text-xs text-text-muted">
          Найдено <strong className="text-text-secondary">{data.total}</strong> кандидатов · пул ≤ 1 000
          {data.recommended_categories?.length > 0 && <> · лучшие категории: {data.recommended_categories.map(
            (c: { role: string; grade: string; candidates: number }) => `${c.role} ${c.grade} (${c.candidates})`).join(', ')}</>}
        </p>
      )}

      {isFetching && !data && (
        <div className="space-y-4">
          {[1,2,3].map(i => <div key={i} className="skeleton h-40" />)}
        </div>
      )}

      {cards.map(card => (
        <CandidateCard key={card.candidate_id} card={card} onOffer={setOfferFor} />
      ))}

      {offerFor && <OfferModal candidateId={offerFor} onClose={() => setOfferFor(null)} />}
    </div>
  )
}

export function OfferModal({ candidateId, onClose }: { candidateId: string; onClose: () => void }) {
  const [form, setForm] = useState({
    role: 'Backend-разработчик',
    salary_from_gross: 150_000,
    salary_to_gross:   250_000,
    work_format: 'remote',
    message: '',
    contact_method: '',
  })
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => createOffer({ ...form, candidate_id: candidateId }),
    onSuccess:  onClose,
    onError:   (e) => setError(apiError(e, 'Не удалось отправить')),
  })

  const send = () => {
    if (form.role.trim().length < 2) return setError('Укажите роль')
    if (form.salary_from_gross <= 0 || form.salary_to_gross < form.salary_from_gross)
      return setError('Проверьте вилку зарплаты')
    if (form.contact_method.trim().length < 3) return setError('Укажите, как кандидату связаться с вами')
    setError('')
    mut.mutate()
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in"
      role="dialog" aria-modal aria-label="Отправить оффер"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="card w-full max-w-md space-y-4 animate-fade-up">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">Оффер кандидату</h2>
          <button onClick={onClose} className="btn-ghost w-8 h-8 p-0" aria-label="Закрыть"><X size={16}/></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-text-muted block mb-1">Роль</label>
            <input value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="input" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-text-muted block mb-1">З/п от (гросс)</label>
              <input type="number" value={form.salary_from_gross}
                onChange={e => setForm({ ...form, salary_from_gross: +e.target.value })} className="input" />
            </div>
            <div>
              <label className="text-xs text-text-muted block mb-1">З/п до (гросс)</label>
              <input type="number" value={form.salary_to_gross}
                onChange={e => setForm({ ...form, salary_to_gross: +e.target.value })} className="input" />
            </div>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Формат</label>
            <select value={form.work_format} onChange={e => setForm({ ...form, work_format: e.target.value })} className="select">
              <option value="remote">удалённо</option>
              <option value="hybrid">гибрид</option>
              <option value="office">офис</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Как связаться с вами</label>
            <input value={form.contact_method} onChange={e => setForm({ ...form, contact_method: e.target.value })}
              className="input" placeholder="Email или Telegram рекрутера" />
          </div>
          <div>
            <label className="text-xs text-text-muted block mb-1">Сообщение кандидату</label>
            <textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })}
              rows={3} className="input resize-none" placeholder="Необязательно" />
          </div>
        </div>

        {error && <p className="text-sm text-rose-400" role="alert">{error}</p>}

        <div className="flex gap-3 pt-1">
          <button onClick={send} className="btn-primary flex-1">
            {mut.isPending ? 'Отправляем…' : 'Отправить'}
          </button>
          <button onClick={onClose} className="btn-secondary flex-1">Отмена</button>
        </div>
      </div>
    </div>
  )
}
