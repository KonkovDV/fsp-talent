import { useState } from 'react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Search as SearchIcon, Sparkles } from 'lucide-react'
import { parseQuery, searchCandidates } from '../../api/client'
import { DISC_RU, ROLE_RU } from '../../labels'
import CandidateCard, { type CandidateCardData } from '../../components/CandidateCard'
import InviteDialog from '../../components/InviteDialog'
import { Empty, PageHeader, Skeleton, plural } from '../../components/ui'

const ROLES = ['backend', 'frontend', 'fullstack', 'ml', 'devops', 'security', 'embedded', 'mobile']
const GRADES = ['junior', 'middle', 'senior', 'lead']
const DISCS = ['algorithmic', 'product', 'security', 'bas', 'robotics', 'ai']
const RANKS = ['МС', 'КМС', 'I', 'II', 'III']
const EXAMPLES = ['senior backend Python Kafka', 'middle фронтенд React TypeScript', 'специалист по ИБ с КМС']

type Params = Record<string, string | boolean | undefined>

/** Free search over the anonymous base. The explainable score orders the list; filters narrow it. */
export default function EmployerSearch() {
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [grade, setGrade] = useState('')
  const [discipline, setDiscipline] = useState('')
  const [minRank, setMinRank] = useState('')
  const [skills, setSkills] = useState('')
  const [assessedOnly, setAssessedOnly] = useState(false)
  const [hasFsp, setHasFsp] = useState('')
  const [internship, setInternship] = useState(false)
  const [inviteFor, setInviteFor] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  const params: Params = {
    q: q || undefined, role: role || undefined, grade: grade || undefined, discipline: discipline || undefined,
    min_rank: minRank || undefined, skills: skills || undefined, assessed_only: assessedOnly || undefined,
    has_fsp: hasFsp || undefined, work_goal: internship ? 'internship' : undefined,
  }
  // Filters edit a draft; the list on screen changes only on «Найти» and stays visible while the new one loads.
  const [submitted, setSubmitted] = useState<Params>({})
  const { data, isFetching, isLoading } = useQuery({
    queryKey: ['search', submitted],
    queryFn: () => searchCandidates(submitted).then(r => r.data),
    placeholderData: keepPreviousData,
  })
  const draftChanged = JSON.stringify(submitted) !== JSON.stringify(params)
  const run = () => setSubmitted({ ...params })

  const parsed = useMutation({
    mutationFn: () => parseQuery(q).then(r => r.data),
    onSuccess: res => {
      if (res.role) setRole(res.role)
      if (res.grade) setGrade(res.grade)
      if (res.discipline) setDiscipline(res.discipline)
      if (res.skills?.length) setSkills(res.skills.join(', '))
    },
  })
  const cards: CandidateCardData[] = data?.items ?? []
  const label = 'field-label'

  return (
    <div>
      <PageHeader title="Поиск кандидатов"
        lead="Карточки анонимны: имя и контакты откроются, когда кандидат примет приглашение. Порядок задаёт один скор, его разбор — в каждой карточке." />

      <form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); run() }} role="search">
        <div className="relative min-w-0 flex-1 basis-72">
          <SearchIcon size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Кого ищете? Например: middle backend, Python, PostgreSQL"
            className="input py-3 pl-11 text-base" aria-label="Запрос" />
        </div>
        <button type="button" onClick={() => parsed.mutate()} disabled={!q || parsed.isPending} className="btn-secondary py-3"
          title="Разложить запрос на роль, грейд и навыки">
          <Sparkles size={16} aria-hidden /> {parsed.isPending ? 'Разбираем…' : 'Разобрать запрос'}
        </button>
        <button type="submit" className="btn-primary px-6 py-3">{isFetching ? 'Ищем…' : 'Найти'}</button>
      </form>
      {!q && (
        <p className="mt-2 text-xs text-ink-3">Например:{' '}
          {EXAMPLES.map((ex, i) => <span key={ex}>{i > 0 && ', '}<button type="button" className="text-accent hover:underline" onClick={() => setQ(ex)}>{ex}</button></span>)}
        </p>
      )}

      <div className="mt-8 grid items-start gap-8 lg:grid-cols-[260px_1fr]">
        <button type="button" onClick={() => setShowFilters(v => !v)} aria-expanded={showFilters} className="btn-secondary lg:hidden">
          {showFilters ? 'Скрыть фильтры' : 'Фильтры'}
        </button>
        <aside className={`${showFilters ? 'block' : 'hidden'} space-y-4 lg:sticky lg:top-36 lg:block`} aria-label="Фильтры">
          <div><label className={label} htmlFor="f-role">Специализация</label>
            <select id="f-role" value={role} onChange={e => setRole(e.target.value)} className="select">
              <option value="">Любая</option>{ROLES.map(v => <option key={v} value={v}>{ROLE_RU[v]}</option>)}
            </select></div>
          <div><label className={label} htmlFor="f-grade">Грейд</label>
            <select id="f-grade" value={grade} onChange={e => setGrade(e.target.value)} className="select">
              <option value="">Любой</option>{GRADES.map(v => <option key={v} value={v}>{v}</option>)}
            </select></div>
          <div><label className={label} htmlFor="f-skills">Навыки</label>
            <input id="f-skills" value={skills} onChange={e => setSkills(e.target.value)} placeholder="Через запятую" className="input" /></div>
          <div><label className={label} htmlFor="f-disc">Дисциплина ФСП</label>
            <select id="f-disc" value={discipline} onChange={e => setDiscipline(e.target.value)} className="select">
              <option value="">Любая</option>{DISCS.map(v => <option key={v} value={v}>{DISC_RU[v]}</option>)}
            </select></div>
          <div><label className={label} htmlFor="f-rank">Разряд не ниже</label>
            <select id="f-rank" value={minRank} onChange={e => setMinRank(e.target.value)} className="select">
              <option value="">Не важно</option>{RANKS.map(v => <option key={v} value={v}>{v}</option>)}
            </select></div>
          <div><label className={label} htmlFor="f-fsp">История ФСП</label>
            <select id="f-fsp" value={hasFsp} onChange={e => setHasFsp(e.target.value)} className="select" aria-label="История ФСП">
              <option value="">Не важно</option><option value="true">Есть</option><option value="false">Нет</option>
            </select></div>
          <fieldset className="space-y-2.5 pt-1 text-sm text-ink">
            <label className="flex items-center gap-2"><input type="checkbox" checked={assessedOnly} onChange={e => setAssessedOnly(e.target.checked)} />Только грейд, подтверждённый тестом</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={internship} onChange={e => setInternship(e.target.checked)} />Ищут стажировку или практику</label>
          </fieldset>
          {draftChanged && <button onClick={run} className="btn-primary w-full">Применить фильтры</button>}
        </aside>

        <section aria-live="polite" aria-busy={isFetching} className="min-w-0">
          {sent && <p className="notice-ok mb-4" role="status">Приглашение отправлено. Ответ кандидата появится в разделе «Приглашения».</p>}
          {data && (
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
              <p className="text-sm text-ink-2"><span className="num font-semibold text-ink">{data.total}</span> {plural(data.total, ['кандидат', 'кандидата', 'кандидатов'])}{draftChanged && ' — фильтры изменены, список ещё прежний'}</p>
              {data.recommended_categories?.length > 0 && (
                <p className="flex flex-wrap items-center gap-2 text-xs text-ink-3">Сильнее всего:
                  {data.recommended_categories.map((c: { role: string; grade: string; candidates: number }) => (
                    <button key={`${c.role}-${c.grade}`} className="chip-default hover:border-accent hover:text-accent"
                      onClick={() => { setRole(c.role ?? ''); setGrade(c.grade ?? ''); setSubmitted({ ...params, role: c.role, grade: c.grade }) }}>
                      {ROLE_RU[c.role] ?? c.role} {c.grade} <span className="num text-ink-3">{c.candidates}</span>
                    </button>
                  ))}
                </p>
              )}
            </div>
          )}
          {isLoading && <div className="space-y-4"><Skeleton className="h-48" /><Skeleton className="h-48" /></div>}
          {data && cards.length === 0 && <Empty title="Никого не нашли">Ослабьте фильтры: например, уберите разряд или грейд. Кандидаты без истории ФСП тоже есть в базе.</Empty>}
          <div className={`space-y-4 transition-opacity ${isFetching ? 'opacity-60' : ''}`}>
            {cards.map((card, i) => <CandidateCard key={card.candidate_id} card={card} place={i + 1} onOffer={setInviteFor} />)}
          </div>
        </section>
      </div>
      {inviteFor && <InviteDialog candidateId={inviteFor} defaultRole={role ? `${ROLE_RU[role]}-разработчик` : ''}
        onClose={() => setInviteFor(null)} onSent={() => setSent(true)} />}
    </div>
  )
}
