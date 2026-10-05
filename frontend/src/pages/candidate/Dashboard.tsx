import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMyProfile, getMyOffers } from '../../api/client'
import GradeRadar from '../../components/GradeRadar'
import ScoreBar from '../../components/ScoreBar'
import SurveyCard from '../../components/SurveyCard'
import { roleRu } from '../../labels'
import { Trophy, Briefcase, Eye, TrendingUp, ShieldCheck } from 'lucide-react'

const GRADE_BADGE: Record<string, string> = {
  lead:   'badge-lead',
  senior: 'badge-senior',
  middle: 'badge-middle',
  junior: 'badge-junior',
}

const SOURCE_LABEL: Record<string, string> = {
  assessed:   'подтверждён тестом',
  declared:   'указан вами',
  experience: 'по опыту',
  default:    'не указан',
}

export default function CandidateDashboard() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ['myProfile'],
    queryFn:  () => getMyProfile().then(r => r.data),
  })
  const { data: offers = [] } = useQuery({
    queryKey: ['myOffers'],
    queryFn:  () => getMyOffers().then(r => r.data),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-8 w-40" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[1,2,3,4].map(i => <div key={i} className="skeleton h-28" />)}
        </div>
        <div className="grid md:grid-cols-2 gap-6">
          <div className="skeleton h-64" />
          <div className="skeleton h-64" />
        </div>
      </div>
    )
  }
  if (!profile) return null

  const pending  = (offers as { status: string }[]).filter(o => o.status === 'pending').length
  const topDisc  = profile.discipline_scores?.[0]

  const stats = [
    {
      icon: Trophy,
      label: 'Дисциплины ФСП',
      value: profile.discipline_scores?.length ?? 0,
      accent: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      delta: null,
    },
    {
      icon: Briefcase,
      label: 'Новые офферы',
      value: pending,
      accent: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
      delta: pending > 0 ? `+${pending} ждут` : null,
    },
    {
      icon: Eye,
      label: 'В поиске',
      value: profile.discoverable ? 'да' : 'нет',
      accent: profile.discoverable ? 'text-emerald-400' : 'text-text-muted',
      bg: profile.discoverable ? 'bg-emerald-500/10' : 'bg-surface-2',
      delta: null,
    },
    {
      icon: TrendingUp,
      label: 'Байесовский μ',
      value: topDisc ? (topDisc.mu ?? topDisc.lcb)?.toFixed(2) : '—',
      accent: 'text-brand-bright',
      bg: 'bg-brand/10',
      delta: topDisc ? `LCB ${topDisc.lcb?.toFixed(2)}` : null,
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Кабинет</h1>
          {profile.scoring_version && (
            <p className="text-xs text-text-muted mt-1">scoring {profile.scoring_version}</p>
          )}
        </div>
        {profile.grade && (
          <span className={GRADE_BADGE[profile.grade] ?? 'badge-junior'}>{profile.grade}</span>
        )}
      </div>

      {!profile.survey_done && <SurveyCard profile={profile} />}

      {profile.survey_done && profile.grade_source !== 'assessed' && (
        <div className="card flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm">
            Грейд не подтверждён тестом. Работодатели ставят подтверждённый грейд выше самооценки.
          </p>
          <Link to="/candidate/assessment" className="btn-primary text-sm">Пройти тест на грейд</Link>
        </div>
      )}

      {/* Stats grid */}
      <section aria-label="Статистика">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map(({ icon: Icon, label, value, accent, bg, delta }) => (
            <div key={label} className="stat-card">
              <div className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center shrink-0`}>
                <Icon size={18} className={accent} aria-hidden />
              </div>
              <p className={`stat-card-value ${accent}`}>{value}</p>
              <p className="stat-card-label">{label}</p>
              {delta && <p className="stat-card-delta text-text-muted">{delta}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* Main content */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Discipline scores */}
        <section className="card space-y-5" aria-labelledby="scores-heading">
          <div className="flex items-center justify-between">
            <h2 id="scores-heading" className="font-semibold text-text-primary">Дисциплинарные скоры</h2>
            <ShieldCheck size={16} className="text-text-muted" />
          </div>
          {(profile.discipline_scores ?? []).length > 0 ? (
            <div className="space-y-5">
              {(profile.discipline_scores ?? []).map((ds: {
                discipline: string; label: string;
                score?: number; mu?: number; lcb: number; sigma?: number; best_rank: string | null
              }) => (
                <div key={ds.discipline} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-text-primary">{ds.label}</p>
                    {ds.best_rank && (
                      <span className={`text-2xs ${ds.best_rank.includes('КМС') ? 'badge-kmc' : ds.best_rank.includes('МС') ? 'badge-mc' : 'badge-junior'}`}>
                        {ds.best_rank}
                      </span>
                    )}
                  </div>
                  <ScoreBar mu={ds.score ?? ds.mu ?? ds.lcb} lcb={ds.lcb} sigma={ds.sigma} compact />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted">Результаты соревнований не добавлены.</p>
          )}
          <GradeRadar scores={profile.discipline_scores ?? []} />
        </section>

        {/* Profile / skills */}
        <section className="card space-y-5" aria-labelledby="profile-heading">
          <h2 id="profile-heading" className="font-semibold text-text-primary">Навыки и роль</h2>

          <div className="flex flex-wrap gap-1.5">
            {(profile.stack ?? []).map((sk: string) => (
              <span key={sk} className="chip chip-active">{sk}</span>
            ))}
          </div>

          <dl className="space-y-2 text-sm">
            <div className="flex gap-2">
              <dt className="text-text-muted w-24 shrink-0">Роль</dt>
              <dd className="font-medium text-text-primary">{roleRu(profile.primary_role)}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-text-muted w-24 shrink-0">Грейд</dt>
              <dd className="font-medium text-text-primary">
                {profile.grade ?? '—'}
                {profile.grade_source && (
                  <span className="text-text-muted font-normal ml-1">({SOURCE_LABEL[profile.grade_source] ?? profile.grade_source})</span>
                )}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-text-muted w-24 shrink-0">Регион</dt>
              <dd className="font-medium text-text-primary">{profile.region ?? '—'}</dd>
            </div>
          </dl>

          {(profile.explanation ?? []).length > 0 && (
            <div className="space-y-1 pt-2 border-t border-border">
              {(profile.explanation as string[]).map(line => (
                <p key={line} className="text-xs text-text-muted">{line}</p>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
