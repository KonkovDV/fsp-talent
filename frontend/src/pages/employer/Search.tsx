import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiError, createOffer, parseQuery, searchCandidates } from '../../api/client'
import { DISC_RU, ROLE_RU } from '../../labels'
import { Search } from 'lucide-react'

const ROLES = ['', 'backend', 'frontend', 'fullstack', 'ml', 'devops', 'security', 'embedded', 'mobile']
const GRADES = ['', 'junior', 'middle', 'senior', 'lead']
const DISCS = ['', 'algorithmic', 'product', 'security', 'bas', 'robotics']
const RANKS = ['', 'МС', 'КМС', 'I', 'II', 'III']

export default function EmployerSearch() {
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [grade, setGrade] = useState('')
  const [discipline, setDiscipline] = useState('')
  const [minRank, setMinRank] = useState('')
  const [skills, setSkills] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [offerFor, setOfferFor] = useState<string | null>(null)

  const params = {
    q: q || undefined, role: role || undefined, grade: grade || undefined,
    discipline: discipline || undefined, min_rank: minRank || undefined, skills: skills || undefined,
  }
  const { data, isFetching } = useQuery({
    queryKey: ['search', params],
    queryFn: () => searchCandidates(params).then(r => r.data),
    enabled,
  })
  const parsed = useMutation({
    mutationFn: () => parseQuery(q).then(r => r.data),
    onSuccess: (result) => {
      if (result.role) setRole(result.role)
      if (result.grade) setGrade(result.grade)
      if (result.discipline) setDiscipline(result.discipline)
      if (result.skills?.length) setSkills(result.skills.join(', '))
    },
  })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Поиск кандидатов</h1>
      <p className="text-sm text-gray-500">Карточки анонимны. Имя и контакты открываются только после согласия кандидата.</p>
      <div className="card space-y-3">
        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-60 relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={q} onChange={e => { setQ(e.target.value); setEnabled(false) }}
              onKeyDown={e => e.key === 'Enter' && setEnabled(true)}
              placeholder="сеньор бэкенд, Python, чемпионат"
              className="w-full border border-gray-200 rounded-xl pl-9 pr-4 py-2.5 text-sm" />
          </div>
          <button onClick={() => parsed.mutate()} disabled={!q || parsed.isPending} className="btn-secondary text-sm">
            Разобрать запрос
          </button>
          <button onClick={() => setEnabled(true)} className="btn-primary text-sm">
            {isFetching ? 'Ищем…' : 'Найти'}
          </button>
        </div>
        <div className="flex gap-3 flex-wrap">
          <select value={role} onChange={e => { setRole(e.target.value); setEnabled(false) }} className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            {ROLES.map(item => <option key={item} value={item}>{item ? ROLE_RU[item] : 'Любая роль'}</option>)}
          </select>
          <select value={grade} onChange={e => { setGrade(e.target.value); setEnabled(false) }} className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            {GRADES.map(item => <option key={item} value={item}>{item || 'Любой грейд'}</option>)}
          </select>
          <select value={discipline} onChange={e => { setDiscipline(e.target.value); setEnabled(false) }} className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            {DISCS.map(item => <option key={item} value={item}>{item ? DISC_RU[item] : 'Любая дисциплина'}</option>)}
          </select>
          <select value={minRank} onChange={e => { setMinRank(e.target.value); setEnabled(false) }} className="border border-gray-200 rounded-xl px-3 py-2 text-sm">
            {RANKS.map(item => <option key={item} value={item}>{item ? `разряд от ${item}` : 'Любой разряд'}</option>)}
          </select>
          <input value={skills} onChange={e => { setSkills(e.target.value); setEnabled(false) }}
            placeholder="Навыки через запятую" className="border border-gray-200 rounded-xl px-3 py-2 text-sm min-w-52" />
        </div>
      </div>

      {enabled && data && <p className="text-sm text-gray-500">В выборке {data.total}. Показаны анонимные карточки.</p>}
      {data?.items?.map((card: Card) => (
        <article key={card.candidate_id} className="card space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-semibold">{ROLE_RU[card.role ?? ''] ?? card.role ?? 'Роль не определена'} · {card.grade ?? '—'}</p>
              <p className="text-sm text-gray-500">
                {card.region ?? 'регион не указан'}
                {card.experience_years != null ? ` · опыт ${card.experience_years} лет` : ''}
                {card.grade_source === 'declared' ? ' · грейд указан кандидатом' : ''}
              </p>
            </div>
            <button onClick={() => setOfferFor(card.candidate_id)} className="btn-primary text-xs py-1.5 px-4">Оффер</button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {card.stack.map(skill => (
              <span key={skill} className={`px-2 py-0.5 rounded text-xs ${card.matched_skills.includes(skill) ? 'bg-fsp-violet/15 text-fsp-violet' : 'bg-gray-100 text-gray-700'}`}>{skill}</span>
            ))}
            {card.missing_skills.map(skill => (
              <span key={skill} className="px-2 py-0.5 rounded text-xs bg-red-50 text-red-700">нет {skill}</span>
            ))}
          </div>
          <ul className="text-sm text-gray-600 space-y-1">
            {card.why.map(line => <li key={line}>{line}</li>)}
          </ul>
          {card.disciplines[0] && (
            <p className="text-xs text-gray-400 font-mono">
              {card.disciplines[0].label}: LCB {card.disciplines[0].lcb.toFixed(2)}
              {card.disciplines[0].best_rank ? ` · ${card.disciplines[0].best_rank}` : ''}
              {card.disciplines[0].evidence.map(item => ` · ${item.status} ${item.year}, ${item.bucket}${item.team ? ', команда' : ''}`).join('')}
            </p>
          )}
        </article>
      ))}
      {offerFor && <OfferForm candidateId={offerFor} onClose={() => setOfferFor(null)} />}
    </div>
  )
}

interface Card {
  candidate_id: string
  role: string | null
  grade: string | null
  grade_source: string | null
  region: string | null
  experience_years: number | null
  stack: string[]
  matched_skills: string[]
  missing_skills: string[]
  why: string[]
  disciplines: { label: string; lcb: number; best_rank: string | null; evidence: { status: string; year: number; bucket: string; team: boolean }[] }[]
}

function OfferForm({ candidateId, onClose }: { candidateId: string; onClose: () => void }) {
  const [form, setForm] = useState({ role: 'Backend-разработчик', salary_from_gross: 150000, salary_to_gross: 250000, work_format: 'remote', message: '' })
  const [localError, setLocalError] = useState('')
  const mut = useMutation({
    mutationFn: () => createOffer({ ...form, candidate_id: candidateId }),
    onSuccess: onClose,
    onError: (error) => setLocalError(apiError(error, 'Не удалось отправить')),
  })
  const send = () => {
    if (form.role.trim().length < 2) return setLocalError('Укажите роль')
    if (form.salary_from_gross <= 0 || form.salary_to_gross < form.salary_from_gross) return setLocalError('Проверьте вилку зарплаты')
    setLocalError('')
    mut.mutate()
  }
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md space-y-4">
        <h2 className="text-lg font-bold">Оффер с зарплатой</h2>
        <input value={form.role} onChange={e => setForm({ ...form, role: e.target.value })} className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
        <div className="flex gap-3">
          <input type="number" value={form.salary_from_gross} onChange={e => setForm({ ...form, salary_from_gross: +e.target.value })} className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
          <input type="number" value={form.salary_to_gross} onChange={e => setForm({ ...form, salary_to_gross: +e.target.value })} className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
        </div>
        <select value={form.work_format} onChange={e => setForm({ ...form, work_format: e.target.value })} className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm">
          <option value="remote">удалённо</option>
          <option value="hybrid">гибрид</option>
          <option value="office">офис</option>
        </select>
        <textarea value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} rows={3} placeholder="Сообщение кандидату" className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm" />
        {localError && <p className="text-sm text-fsp-red">{localError}</p>}
        <div className="flex gap-3">
          <button onClick={send} className="btn-primary flex-1">{mut.isPending ? 'Отправляем…' : 'Отправить'}</button>
          <button onClick={onClose} className="btn-secondary flex-1">Отмена</button>
        </div>
      </div>
    </div>
  )
}
