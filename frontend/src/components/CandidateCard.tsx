import { useState } from 'react'
import ScoreBar from './ScoreBar'
import { ROLE_RU } from '../labels'
import { Trophy, MapPin, Clock, ChevronDown, ChevronUp, Send } from 'lucide-react'

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
  disciplines: {
    label: string
    discipline: string
    mu: number
    lcb: number
    sigma?: number
    best_rank: string | null
    evidence: { status: string; year: number; bucket: string; team: boolean }[]
  }[]
}

/** Grade → badge class (ФСП palette) */
const GRADE_BADGE: Record<string, string> = {
  lead:   'badge-lead',
  senior: 'badge-senior',
  middle: 'badge-middle',
  junior: 'badge-junior',
}

/** Grade → left-border accent color */
const GRADE_BORDER: Record<string, string> = {
  lead:   '#F0A500',   // Gold
  senior: '#1D82F5',   // Electric blue
  middle: '#1B3FA0',   // Brand blue
  junior: '#6B7280',   // Grey
}

function rankBadgeClass(rank: string | null): string {
  if (!rank) return ''
  if (rank.includes('КМС') || rank.includes('kmc')) return 'badge-kmc'
  if (rank.includes('МС')  || rank.includes('mc'))  return 'badge-mc'
  return 'badge-vc'
}

interface Props {
  card: CandidateCardData
  onOffer: (id: string) => void
}

export default function CandidateCard({ card, onOffer }: Props) {
  const [expanded, setExpanded] = useState(false)
  const disc = card.disciplines[0]

  const gradeBadge  = card.grade ? GRADE_BADGE[card.grade]  ?? 'badge-junior' : ''
  const rankBadge   = disc?.best_rank ? rankBadgeClass(disc.best_rank) : ''
  const borderColor = card.grade ? GRADE_BORDER[card.grade] ?? '#6B7280'       : '#1B3FA0'

  return (
    <article
      className="card cursor-default animate-fade-up space-y-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-card-hover"
      style={{ borderLeft: `3px solid ${borderColor}` }}
    >
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h3 className="text-base font-bold text-text-primary">
              {ROLE_RU[card.role ?? ''] ?? card.role ?? 'Роль не указана'}
            </h3>
            {card.grade && <span className={gradeBadge}>{card.grade}</span>}
            {disc?.best_rank && <span className={rankBadge}>{disc.best_rank}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted">
            {card.region && (
              <span className="flex items-center gap-1">
                <MapPin size={11} aria-hidden />{card.region}
              </span>
            )}
            {card.experience_years != null && (
              <span className="flex items-center gap-1">
                <Clock size={11} aria-hidden />опыт {card.experience_years} лет
              </span>
            )}
            {disc && (
              <span className="flex items-center gap-1">
                <Trophy size={11} aria-hidden />{disc.label}
              </span>
            )}
          </div>
        </div>

        {/* Offer button — ФСП Red */}
        <button
          onClick={() => onOffer(card.candidate_id)}
          className="btn gap-1.5 text-xs py-2 px-4 rounded-md font-bold shrink-0 text-white"
          style={{ background: '#D42330' }}
          aria-label={`Отправить оффер кандидату ${card.candidate_id}`}
        >
          <Send size={12} aria-hidden /> Оффер
        </button>
      </div>

      {/* ── Bayesian scores ── */}
      {disc && <ScoreBar mu={disc.mu} lcb={disc.lcb} sigma={disc.sigma} compact />}

      {/* ── Skills ── */}
      {(card.stack.length > 0 || card.missing_skills.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {card.stack.map(skill => (
            <span
              key={skill}
              className={card.matched_skills.includes(skill) ? 'chip-active' : 'chip-default'}
            >
              {skill}{card.matched_skills.includes(skill) && <span aria-hidden> ✓</span>}
            </span>
          ))}
          {card.missing_skills.map(skill => (
            <span
              key={skill}
              className="chip"
              style={{ background: 'rgba(212,35,48,0.08)', border: '1px solid rgba(212,35,48,0.3)', color: '#FF6B75' }}
            >
              нет {skill}
            </span>
          ))}
        </div>
      )}

      {/* ── Why / evidence toggle ── */}
      {(card.why.length > 0 || disc?.evidence?.length) && (
        <div>
          <button
            onClick={() => setExpanded(e => !e)}
            className="btn-ghost px-0 text-xs gap-1"
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp size={13} aria-hidden /> : <ChevronDown size={13} aria-hidden />}
            {expanded ? 'Скрыть детали' : 'Почему в выдаче'}
          </button>
          {expanded && (
            <div className="mt-2 space-y-1 pl-4" style={{ borderLeft: `2px solid ${borderColor}40` }}>
              {card.why.map(line => (
                <p key={line} className="text-xs text-text-secondary">{line}</p>
              ))}
              {disc?.evidence?.map(ev => (
                <p key={`${ev.year}-${ev.status}`} className="text-xs text-text-muted font-mono">
                  {ev.status} {ev.year} · {ev.bucket}{ev.team ? ' · команда' : ''}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  )
}
