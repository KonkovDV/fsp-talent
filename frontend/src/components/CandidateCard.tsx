import type React from 'react'
import { useState } from 'react'
import { ChevronDown, ClipboardList, Columns3, Heart, Star } from 'lucide-react'
import { JOB_SEARCH_BADGE, ROLE_RU, gradeRu } from '../labels'
import { CategoryPlate, Meter, RankBadge } from './ui'

export interface CandidateCardData {
  candidate_id: string
  role: string | null
  grade: string | null
  grade_source: string | null
  also_primary?: { role: string | null; grade: string | null; grade_source: string | null } | null
  region: string | null
  experience_years: number | null
  stack: string[]
  /** The note of the extra resume this card was found by. */
  resume_summary?: string | null
  matched_skills: string[]
  missing_skills: string[]
  skill_evidence?: Record<string, string>
  why: string[]
  shortlisted?: boolean
  match?: {
    score: number
    basis?: 'fit' | 'evidence'
    employer?: number
    accept?: number | null
    congestion?: number
    reply?: { p: number; label: string } | null
    plus: string[]
    minus: string[]
    info: string[]
    reasons?: { code: string; text: string; tone: string; source?: string | null; points?: number | null }[]
    factors: { key: string; label: string; weight: number; value: number | null; contrib?: number | null }[]
  }
  disciplines: {
    label: string
    discipline: string
    score?: number
    mu?: number
    lcb: number
    confidence?: number
    best_rank: string | null
    rank_assigned_at?: string | null
    rank_order_ref?: string | null
    events_count?: number
    evidence: { status: string; year: number; bucket: string; team: boolean }[]
  }[]
}

const REASON_RU: Record<string, string> = {
  CATEGORY_MATCH: 'Категория совпала',
  VERIFIED_SKILL: 'Навык подтверждён',
  TEST_SCORE: 'Результат теста',
  SKILL_GAP: 'Нет навыка',
  FSP_BONUS: 'Протокол ФСП',
  FSP_SCORE: 'Результаты ФСП',
  COLD_SEAT: 'Место для кандидата без теста (правило разнообразия)',
  FSP_NEUTRAL: 'Без истории ФСП',
  FSP_RELEVANT: 'Профильная дисциплина',
  FSP_OTHER: 'Другая дисциплина',
  RELATED_ROLE: 'Смежная специализация',
  RELATED_SKILL: 'Близкая технология',
  SKILL_COVERAGE: 'Навыки',
  GRADE_DECLARED: 'Грейд заявлен',
  GRADE_ABOVE: 'Грейд выше',
  GRADE_BELOW: 'Грейд ниже',
  OTHER_ROLE: 'Другая специализация',
  UNTESTED: 'Тест не пройден',
  INDUSTRY: 'Предметная область',
  PAY_FIT: 'Вилка сходится',
  PAY_LOW: 'Вилка ниже',
  PAY_GAP: 'Вилка не сходится',
  SALARY_HISTORY: 'Отказ из-за вилки',
  CONGESTION: 'Много приглашений',
  ...JOB_SEARCH_BADGE,
}

interface Props {
  card: CandidateCardData
  place?: number
  onOffer: (id: string) => void
  /** «Дать задание»: a task addressed to this candidate only. */
  onTask?: (id: string) => void
  onShortlist?: (id: string, on: boolean) => void
  /** Company favorites, kept apart from any need. */
  favorite?: { on: boolean; toggle: (id: string, on: boolean) => void }
  /** Side-by-side comparison of up to four cards from the same list. */
  compare?: { on: boolean; full: boolean; toggle: () => void }
}

const years = (n: number) => (n % 10 === 1 && n % 100 !== 11 ? 'год' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'года' : 'лет')

function skillChip(name: string, evidence?: Record<string, string>): string {
  const trust = evidence?.[name]
  if (trust === 'test_confirmed') return `${name}, тест`
  if (trust === 'resume_confirmed') return `${name}, резюме`
  return name
}

/**
 * One line of the selection protocol: place, category, match score and the factors behind it.
 * The card is anonymous: no name, no FSP id, no event names — those open after the candidate's consent.
 */
// Fresh signals: what the candidate did recently. Shown even when the match lines replace «why».
const FRESH = ['Задание работодателя', 'Короткая практика']

function barShares(contribs: number[], employer: number): number[] {
  const target = Math.round(employer * 1000) / 10
  const shown = contribs.map(part => Math.round(part * 1000) / 10)
  if (!shown.length) return shown
  const drift = Math.round((target - shown.reduce((sum, part) => sum + part, 0)) * 10) / 10
  shown[shown.length - 1] = Math.round((shown[shown.length - 1] + drift) * 10) / 10
  return shown
}

function FactorBars({ match, active, idle }: {
  match: NonNullable<CandidateCardData['match']>
  active: NonNullable<CandidateCardData['match']>['factors']
  idle: NonNullable<CandidateCardData['match']>['factors']
}) {
  const useShare = active.some(factor => factor.contrib != null) && match.employer != null
  const shares = useShare ? barShares(active.map(factor => factor.contrib ?? 0), match.employer ?? 0) : []
  const width = (factor: (typeof active)[number], index: number) => {
    const part = useShare ? Math.max(shares[index], 0.4) : Math.max(factor.weight, 0.06)
    return `minmax(4.5rem,${part.toFixed(3)}fr)`
  }
  return (
    <div className="border-t border-line bg-sunken/50 px-5 py-3.5 sm:px-6">
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 md:[grid-template-columns:var(--cols)]"
        style={{ '--cols': active.map(width).join(' ') } as React.CSSProperties}
        aria-label="Факторы скора">
        {active.map((factor, index) => {
          const caption = useShare
            ? `вклад ${shares[index].toFixed(1)} из ${(Math.round((match.employer ?? 0) * 1000) / 10).toFixed(1)}`
            : `вес ${Math.round(factor.weight * 100)} %`
          return (
            <div key={factor.key} title={`${factor.label}: ${caption}`}>
              <Meter value={useShare ? (factor.contrib ?? 0) / Math.max(match.employer || 0, 1e-9) : factor.value}
                ariaLabel={`${factor.label}: ${caption}`} />
              <p className="mt-1.5 flex items-baseline justify-between gap-2 text-[11px] leading-4 text-ink-3">
                <span className="truncate">{factor.label}</span>
                <span className="num shrink-0 font-medium text-ink-2" data-testid="factor-share">
                  {useShare ? shares[index].toFixed(1) : Math.round((factor.value ?? 0) * 100)}
                </span>
              </p>
            </div>
          )
        })}
      </div>
      {useShare && (
        <p className="mt-2 text-xs text-ink-2">
          <span data-testid="employer-score">Работодатель {(Math.round((match.employer ?? 0) * 1000) / 10).toFixed(1)}</span>
          {match.accept == null ? '. Совпадения по вилке нет' : `. Совпадение по вилке ${(match.accept * 100).toFixed(1)}`}
          {(match.congestion ?? 0) > 0 ? `. Очередь −${((match.congestion ?? 0) * 100).toFixed(1)}` : '. Очереди нет'}
          . Итог — гармоническое среднее минус очередь.
        </p>
      )}
      <p className="mt-2 text-2xs text-ink-3">
        <span className="hidden md:inline">{useShare ? 'Ширина полосы — вклад в оценку работодателя. ' : 'Ширина полосы — вес фактора. '}</span>
        {idle.length > 0 && <>Не учитываются: {idle.map(f => f.label === f.label.toUpperCase() ? f.label : f.label.toLowerCase()).join(', ')}</>}
      </p>
    </div>
  )
}

export default function CandidateCard({ card, place, onOffer, onTask, onShortlist, favorite, compare }: Props) {
  const [open, setOpen] = useState(false)
  const fresh = card.why.filter(l => FRESH.some(p => l.startsWith(p)))
  const employerTask = fresh.find(l => l.startsWith(FRESH[0]))
  const disc = card.disciplines[0]
  const score = card.match ? Math.round(card.match.score * 100) : null
  const active = card.match?.factors.filter(f => f.value != null) ?? []
  const idle = card.match?.factors.filter(f => f.value == null) ?? []

  return (
    <article className="card overflow-hidden p-0" data-testid="candidate-card" data-candidate-id={card.candidate_id}>
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 p-5 sm:grid-cols-[2.75rem_1fr_auto] sm:gap-x-5 sm:p-6">
        {place !== undefined && (
          <span className={`place pt-0.5 text-2xl leading-none ${place <= 3 ? 'text-accent' : 'text-ink-3'}`} aria-label={`Место ${place}`}>{place}</span>
        )}
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <CategoryPlate role={card.role} grade={card.grade} source={card.grade_source} />
            {card.also_primary?.role && (
              <span className="text-xs text-ink-3">
                Основная категория: {ROLE_RU[card.also_primary.role] ?? card.also_primary.role}
                {card.also_primary.grade ? `, ${gradeRu(card.also_primary.grade)}` : ''}
                {card.also_primary.grade_source === 'assessed' ? ', подтверждена тестом' : ', не подтверждена'}
              </span>
            )}
            <span className="text-sm text-ink-2">
              {[card.region, card.experience_years != null ? (card.experience_years === 0 ? 'без опыта' : `опыт ${card.experience_years} ${years(card.experience_years)}`) : null].filter(Boolean).join(', ')}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {card.grade_source === 'assessed'
              ? <span className="badge-ok">Грейд подтверждён тестом</span>
              : <span className="badge-vc">Грейд не подтверждён</span>}
            {disc ? <><RankBadge rank={disc.best_rank} assignedAt={disc.rank_assigned_at} orderRef={disc.rank_order_ref} /><span className="text-ink-2">{disc.label}</span></>
              : <span className="text-ink-3">Без истории ФСП</span>}
          </div>
          {(card.matched_skills.length > 0 || card.missing_skills.length > 0 || card.stack.length > 0) && (
            <div className="flex flex-wrap gap-1.5">
              {card.matched_skills.map(s => <span key={s} className="chip-active">{skillChip(s, card.skill_evidence)}</span>)}
              {card.missing_skills.map(s => <span key={s} className="chip-missing">нет {s}</span>)}
              {card.stack.filter(s => !card.matched_skills.includes(s)).slice(0, 6).map(s => <span key={s} className="chip-default">{skillChip(s, card.skill_evidence)}</span>)}
            </div>
          )}
          {card.resume_summary && (
            <p className="text-sm text-ink-2" data-testid="resume-summary">{card.resume_summary}</p>
          )}
          {employerTask && (
            <p className="flex items-start gap-1.5 text-xs text-ink-2" data-testid="task-signal">
              <ClipboardList size={14} className="mt-px shrink-0 text-accent" aria-hidden />{employerTask}
            </p>
          )}
        </div>
        {score !== null && (
          <div className="col-span-2 flex items-center gap-3 sm:col-span-1 sm:flex-col sm:items-end sm:gap-1 sm:text-right">
            <ScoreRing value={score} />
            <span className="whitespace-nowrap text-xs text-ink-3"
              title={card.match?.basis === 'evidence' ? 'Критериев нет: порядок задают тест и результаты ФСП' : 'Насколько кандидат подходит под критерии'}>
              {card.match?.basis === 'evidence' ? 'сила профиля из 100' : 'совпадение из 100'}
            </span>
          </div>
        )}
      </div>

      {card.match && active.length > 0 && (
        <FactorBars match={card.match} active={active} idle={idle} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 sm:px-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <button onClick={() => setOpen(o => !o)} aria-expanded={open} className="btn-ghost -ml-3 gap-1 text-sm">
            <ChevronDown size={16} className={`transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
            Почему в выдаче
          </button>
          {card.match?.reply && (
            <p data-testid="reply-chance" className="text-xs text-ink-2">
              Ответят: {card.match.reply.label}, {Math.round(card.match.reply.p * 100)} %
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {compare && (
            <button type="button" onClick={compare.toggle} aria-pressed={compare.on} disabled={!compare.on && compare.full}
              title={!compare.on && compare.full ? 'Сравнивать можно до четырёх кандидатов' : undefined}
              className={`btn-secondary btn-sm ${compare.on ? 'border-accent text-accent' : ''}`}>
              <Columns3 size={14} aria-hidden />
              {compare.on ? 'В сравнении' : 'Сравнить'}
            </button>
          )}
          {onShortlist && (
            <button onClick={() => onShortlist(card.candidate_id, !card.shortlisted)} aria-pressed={!!card.shortlisted}
              className={`btn-secondary btn-sm ${card.shortlisted ? 'border-accent text-accent' : ''}`}>
              <Star size={14} className={card.shortlisted ? 'fill-current' : ''} aria-hidden />
              {card.shortlisted ? 'В шорт-листе' : 'В шорт-лист'}
            </button>
          )}
          {favorite && (
            <button type="button" onClick={() => favorite.toggle(card.candidate_id, !favorite.on)} aria-pressed={favorite.on}
              data-testid="favorite-toggle"
              className={`btn-secondary btn-sm ${favorite.on ? 'border-accent text-accent' : ''}`}>
              <Heart size={14} className={favorite.on ? 'fill-current' : ''} aria-hidden />
              {favorite.on ? 'В избранном' : 'В избранное'}
            </button>
          )}
          {onTask && <button onClick={() => onTask(card.candidate_id)} className="btn-secondary btn-sm">Дать задание</button>}
          <button onClick={() => onOffer(card.candidate_id)} className="btn-invite-quiet btn-sm">Пригласить</button>
        </div>
      </div>

      {open && (
        <div className="grid gap-5 border-t border-line bg-sunken/60 px-5 py-4 text-sm sm:grid-cols-2 sm:px-6 motion-safe:animate-rise">
          {card.match ? (
            <div data-testid="match">
              {card.why.filter(line => line.startsWith('Подтверждено ФСП')).map(line => (
                <p key={line} className="mb-2 text-ink-2" data-testid="fsp-line">{line}</p>
              ))}
              {!!card.match.reasons?.length && (
                <ul className="mb-2 flex flex-wrap gap-1.5">
                  {card.match.reasons.map(r => (
                    <li key={`${r.code}-${r.text}`} className={r.tone === 'minus' ? 'badge-warn' : r.tone === 'plus' ? 'badge-ok' : 'badge-vc'}>{REASON_RU[r.code] ?? r.code}{r.source ? ` · ${r.source}` : ''}{r.points ? ` · +${Math.round(r.points * 100)} к баллу` : ''}</li>
                  ))}
                </ul>
              )}
              <ul className="space-y-1">
                {card.match.plus.map(l => <li key={l} className="text-ok">+ {l}</li>)}
                {card.match.minus.map(l => <li key={l} className="text-danger">− {l}</li>)}
                {card.match.info.map(l => <li key={l} className="text-ink-2">{l}</li>)}
                {fresh.map(l => <li key={l} className="text-ink-2">{l}</li>)}
              </ul>
            </div>
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

/** Score out of 100 as a ring: the number reads first, the arc shows how far it is from the top. */
function ScoreRing({ value }: { value: number }) {
  const r = 22, c = 2 * Math.PI * r
  return (
    <span className="relative grid h-14 w-14 shrink-0 place-items-center">
      <svg viewBox="0 0 56 56" className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx="28" cy="28" r={r} fill="none" strokeWidth="4" className="stroke-ink/[0.08] dark:stroke-white/[0.1]" />
        <circle cx="28" cy="28" r={r} fill="none" strokeWidth="4" strokeLinecap="round" className="stroke-accent"
          strokeDasharray={`${(c * Math.max(0, Math.min(100, value))) / 100} ${c}`} />
      </svg>
      <span className="font-display text-xl font-bold tabular-nums text-ink">{value}</span>
    </span>
  )
}
