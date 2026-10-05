import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Target } from 'lucide-react'
import {
  apiError, createNeed, listNeeds, needMatches, needShortlist, removeShortlist, setShortlist, surveyOptions, updateNeed,
} from '../../api/client'
import CandidateCard, { type CandidateCardData } from '../../components/CandidateCard'
import { OfferModal } from './Search'

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

  const { data: opts } = useQuery({ queryKey: ['surveyOptions'], queryFn: () => surveyOptions().then(r => r.data) })
  const { data: needs = [] } = useQuery<Need[]>({ queryKey: ['needs'], queryFn: () => listNeeds().then(r => r.data) })
  useEffect(() => { if (!selected && needs.length) setSelected(needs[0].id) }, [needs, selected])
  const current = needs.find(n => n.id === selected) ?? null
  const matches = useQuery({ queryKey: ['needMatches', selected, current?.version], enabled: !!selected,
    queryFn: () => needMatches(selected!).then(r => r.data) })
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
  const select = 'input text-sm'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Потребности</h1>
          <p className="text-sm text-text-muted">Кого вы ищете. Каждое изменение — новая версия; шорт-лист помнит, по какой версии выбран кандидат.</p>
        </div>
        <button onClick={() => { setEditing('new'); setForm(EMPTY) }} className="btn-primary gap-1 text-sm"><Plus size={14} />Новая</button>
      </div>

      {editing && (
        <form className="card grid sm:grid-cols-3 gap-3" onSubmit={e => { e.preventDefault(); save.mutate() }}>
          <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Название, напр. «Python-бэкенд в платёжную команду»"
            className={`${select} sm:col-span-3`} aria-label="Название" />
          <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className={select} aria-label="Специализация">
            <option value="">Любая специализация</option>
            {Object.entries(opts?.specializations ?? {}).map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
          </select>
          <select value={form.grade} onChange={e => setForm({ ...form, grade: e.target.value })} className={select} aria-label="Грейд">
            <option value="">Любой грейд</option>
            {(opts?.grades ?? []).map((g: string) => <option key={g} value={g}>{g}</option>)}
          </select>
          <select value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} className={select} aria-label="Отрасль">
            <option value="">Отрасль не важна</option>
            {Object.entries(opts?.industries ?? {}).filter(([k]) => k !== 'any').map(([k, v]) => <option key={k} value={k}>{v as string}</option>)}
          </select>
          <input value={form.skills} onChange={e => setForm({ ...form, skills: e.target.value })} placeholder="Обязательные навыки через запятую" className={select} aria-label="Обязательные навыки" />
          <input value={form.nice} onChange={e => setForm({ ...form, nice: e.target.value })} placeholder="Желательные навыки" className={select} aria-label="Желательные навыки" />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.internship} onChange={e => setForm({ ...form, internship: e.target.checked })} />Стажировка / практика</label>
          {error && <p className="text-sm text-fsp-red sm:col-span-3" role="alert">{error}</p>}
          <div className="flex gap-2 sm:col-span-3">
            <button className="btn-primary text-sm" disabled={form.title.length < 2 || save.isPending}>{editing === 'new' ? 'Создать' : 'Сохранить новую версию'}</button>
            <button type="button" className="btn-secondary text-sm" onClick={() => setEditing(null)}>Отмена</button>
          </div>
        </form>
      )}

      {needs.length === 0 && !editing && (
        <div className="card text-sm text-text-secondary flex items-center gap-3"><Target size={18} />Создайте первую потребность — подбор и объяснения появятся сразу.</div>
      )}

      {needs.length > 0 && (
        <div className="flex flex-wrap gap-2" role="tablist">
          {needs.map(n => (
            <button key={n.id} role="tab" aria-selected={n.id === selected} onClick={() => setSelected(n.id)}
              className={`text-sm px-3 py-1.5 rounded-lg border ${n.id === selected ? 'border-fsp-electric text-fsp-electric' : 'border-border text-text-secondary'}`}>
              {n.title} <span className="text-text-muted">v{n.version} · ★{n.shortlist_count}</span>
            </button>
          ))}
        </div>
      )}

      {current && (
        <div className="grid lg:grid-cols-[1fr_280px] gap-6 items-start">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
              <span>{current.params.role ?? 'любая специализация'} · {current.params.grade ?? 'любой грейд'}</span>
              {current.params.skills.map(s => <span key={s} className="chip-default">{s}</span>)}
              {current.params.nice_to_have.map(s => <span key={s} className="chip-default opacity-70">+{s}</span>)}
              <button onClick={() => edit(current)} className="text-fsp-electric hover:underline">изменить</button>
            </div>
            {matches.data?.recommended_categories?.length > 0 && (
              <p className="text-xs text-text-secondary">Где искать: {matches.data.recommended_categories.map(
                (c: { role: string; grade: string; candidates: number; best: number }) => `${c.role} ${c.grade} — ${c.candidates} канд., лучшее совпадение ${Math.round(c.best * 100)}`).join(' · ')}</p>
            )}
            {matches.isLoading && <div className="skeleton h-40" />}
            {(matches.data?.items ?? []).map((card: CandidateCardData) => (
              <CandidateCard key={card.candidate_id} card={card} onOffer={setOfferFor}
                onShortlist={(id, on) => toggle.mutate({ id, on })} />
            ))}
          </div>
          <aside className="card space-y-3 lg:sticky lg:top-20" aria-label="Шорт-лист">
            <p className="font-semibold text-sm">Шорт-лист</p>
            {shortlist.data && (
              <p className="text-xs text-text-muted">Отобрано {shortlist.data.funnel.shortlisted} · приглашено {shortlist.data.funnel.invited} · отказ {shortlist.data.funnel.rejected}</p>
            )}
            <ul className="text-xs space-y-2">
              {(shortlist.data?.items ?? []).map((r: { candidate_id: string; role: string; grade: string; score: number; picked_on_version: number }) => (
                <li key={r.candidate_id} className="flex justify-between gap-2">
                  <span>{r.role} {r.grade} · {Math.round((r.score ?? 0) * 100)}</span>
                  <span className="text-text-muted">v{r.picked_on_version}</span>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      )}
      {offerFor && <OfferModal candidateId={offerFor} onClose={() => setOfferFor(null)} />}
    </div>
  )
}
