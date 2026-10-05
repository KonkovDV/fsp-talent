import { useState } from 'react'
import { ChevronDown, Star } from 'lucide-react'
import { CategoryPlate, Meter, RankBadge } from './ui'

export interface CandidateCardData {
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
  shortlisted?: boolean
  match?: {
    score: number
    plus: string[]
    minus: string[]
    info: string[]
    factors: { key: string; label: string; weight: number; value: number | null }[]
  }
  disciplines: {
    label: string
    discipline: string
    score?: number
    mu?: number
    lcb: number
    confidence?: number
    best_rank: string | null
    events_count?: number
    evidence: { status: string; year: number; bucket: string; team: boolean }[]
  }[]
}

interface Props {
  card: CandidateCardData
  place?: number
  onOffer: (id: string) => void
  onShortlist?: (id: string, on: boolean) => void
}

const years = (n: number) => (n % 10 === 1 && n % 100 !== 11 ? 'год' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'года' : 'лет')

/**
 * One line of the selection protocol: place, category, match score and the factors behind it.
 * The card is anonymous: no name, no FSP id, no event names — those open after the candidate's consent.
 */
export default function CandidateCard({ card, place, onOffer, onShortlist }: Props) {
  const [open, setOpen] = useState(false)
  const disc = card.disciplines[0]
  const score = card.match ? Math.round(card.match.score * 100) : null
  const testFactor = card.match?.factors.find(f => f.key === 'test')

  return (
    <article className="card p-0" data-testid="candidate-card">
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 p-5 sm:grid-cols-[2.5rem_1fr_auto] sm:p-6">
        {place !== undefined && <span className="place pt-0.5 text-ink-3" aria-label={`Место ${place}`}>{place}</span>}
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <CategoryPlate role={card.role} grade={card.grade} source={card.grade_source} />
            <span className="text-sm text-ink-2">
              {[card.region, card.experience_years != null ? (card.experience_years === 0 ? 'без опыта' : `опыт ${card.experience_years} ${years(card.experience_years)}`) : null].filter(Boolean).join(', ')}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {card.grade_source === 'assessed'
              ? <span className="badge-ok">Грейд подтверждён тестом{testFactor?.value != null && testFactor.value !== 0.5 ? `, ${Math.round(testFactor.value * 100)} %` : ''}</span>
              : <span className="badge-vc">Грейд заявлен</span>}
            {disc ? <><RankBadge rank={disc.best_rank} /><span className="text-ink-2">{disc.label}</span></>
              : <span className="text-ink-3">Без истории ФСП</span>}
          </div>
          {(card.matched_skills.length > 0 || card.missing_skills.length > 0 || card.stack.length > 0) && (
            <div className="flex flex-wrap gap-1.5">
              {card.matched_skills.map(s => <span key={s} className="chip-active">{s}</span>)}
              {card.missing_skills.map(s => <span key={s} className="chip-missing">нет {s}</span>)}
              {card.stack.filter(s => !card.matched_skills.includes(s)).slice(0, 6).map(s => <span key={s} className="chip-default">{s}</span>)}
            </div>
          )}
        </div>
        {score !== null && (
          <div className="col-span-2 flex items-baseline gap-2 sm:col-span-1 sm:block sm:text-right">
            <span className="font-display text-3xl font-semibold tabular-nums text-ink">{score}</span>
            <span className="text-xs text-ink-3 sm:block">совпадение из 100</span>
          </div>
        )}
      </div>

      {card.match && (
        <div className="grid grid-cols-4 gap-x-3 gap-y-2 border-t border-line px-5 py-3 sm:grid-cols-7 sm:px-6" aria-label="Факторы совпадения">
          {card.match.factors.map(f => (
            <div key={f.key} title={`${f.label}: ${f.value == null ? 'не учитывается' : Math.round(f.value * 100) + ' %'}; вес ${Math.round(f.weight * 100)} %`}>
              <Meter value={f.value} label={f.label} />
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 sm:px-6">
        <button onClick={() => setOpen(o => !o)} aria-expanded={open} className="btn-ghost -ml-3 gap-1 text-sm">
          <ChevronDown size={16} className={`transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
          Почему в выдаче
        </button>
        <div className="flex gap-2">
          {onShortlist && (
            <button onClick={() => onShortlist(card.candidate_id, !card.shortlisted)} aria-pressed={!!card.shortlisted}
              className={`btn-secondary btn-sm ${card.shortlisted ? 'border-accent text-accent' : ''}`}>
              <Star size={14} className={card.shortlisted ? 'fill-current' : ''} aria-hidden />
              {card.shortlisted ? 'В шорт-листе' : 'В шорт-лист'}
            </button>
          )}
          <button onClick={() => onOffer(card.candidate_id)} className="btn-invite btn-sm">Пригласить</button>
        </div>
      </div>

      {open && (
        <div className="grid gap-5 border-t border-line bg-sunken/60 px-5 py-4 text-sm sm:grid-cols-2 sm:px-6">
          {card.match ? (
            <ul className="space-y-1" data-testid="match">
              {card.match.plus.map(l => <li key={l} className="text-ok">+ {l}</li>)}
              {card.match.minus.map(l => <li key={l} className="text-invite">− {l}</li>)}
              {card.match.info.map(l => <li key={l} className="text-ink-2">{l}</li>)}
            </ul>
          ) : <ul className="space-y-1 text-ink-2">{card.why.map(l => <li key={l}>{l}</li>)}</ul>}
          {disc && disc.evidence.length > 0 && (
            <div>
              <p className="text-xs text-ink-3">Лучшие результаты, {disc.label.toLowerCase()}</p>
              <ul className="mt-1.5 space-y-1 text-ink">
                {disc.evidence.map(ev => (
                  <li key={`${ev.year}-${ev.status}-${ev.bucket}`}>{ev.status} {ev.year}: {ev.bucket}{ev.team ? ', команда' : ''}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </article>
  )
}
