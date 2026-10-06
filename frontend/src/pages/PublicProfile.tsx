import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { getPublicProfile, getCredentials, verifyCredential } from '../api/client'
import { Shield } from 'lucide-react'
import PublicShell from '../components/PublicShell'
import { CategoryPlate, Empty, Meter, RankBadge, Skeleton } from '../components/ui'
import SkillPassport, { type PassportSkill } from '../components/SkillPassport'

interface Achievement {
  eventName?: string
  place?: number
  totalParticipants?: number
  rankEquivalent?: string | null
  discipline?: string
  eventDate?: string
  teamSize?: number
}

export default function PublicProfile() {
  const { id } = useParams<{ id: string }>()
  const profileQuery = useQuery({
    queryKey: ['pub', id],
    queryFn: () => getPublicProfile(id!).then(r => r.data),
    retry: false,
  })
  const { data: creds = [] } = useQuery({
    queryKey: ['creds', id],
    queryFn: () => getCredentials(id!).then(r => r.data),
    enabled: profileQuery.isSuccess,
  })
  const [tamperNote, setTamperNote] = useState<string | null>(null)
  const tamper = useMutation({
    mutationFn: (credential: object) => verifyCredential(credential).then(r => r.data as { valid: boolean }),
    onSuccess: (result) => setTamperNote(result.valid ? 'подпись всё ещё верна' : 'подпись не сходится: место в протоколе изменено'),
  })

  if (profileQuery.isError) {
    return <PublicShell><Empty title="Публичной страницы нет" action={<Link to="/leaderboard" className="btn-secondary">К рейтингу</Link>}>
      Её включает сам участник, и только с 18 лет.</Empty></PublicShell>
  }
  if (!profileQuery.data) return <PublicShell><Skeleton className="h-96" /></PublicShell>
  const profile = profileQuery.data
  const scores: { discipline: string; label: string; lcb: number; confidence?: number; best_rank: string | null }[] = profile.discipline_scores ?? []
  return (
    <PublicShell>
      <div className="grid items-start gap-8 lg:grid-cols-[320px_1fr]">
        <aside className="card">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft font-display text-xl font-bold text-accent" aria-hidden>
            {(profile.display_name ?? 'У')[0]}
          </div>
          <h1 className="mt-4 font-display text-xl font-bold text-ink">{profile.display_name}</h1>
          <p className="mt-1 text-sm text-ink-2">{profile.region}</p>
          <div className="mt-4"><CategoryPlate role={profile.primary_role} grade={profile.grade} source={profile.grade_source} /></div>
          <p className="mt-6 text-xs text-ink-3">Контакты на публичной странице не показываются никогда.</p>
        </aside>
        <div className="space-y-6">
          {(profile.skills ?? []).length > 0 && (
            <section className="card">
              <h2 className="section-title">Паспорт навыков</h2>
              <p className="mt-1 text-sm text-ink-2">Откуда взят навык и насколько ему можно доверять в подборке.</p>
              <SkillPassport skills={profile.skills as PassportSkill[]} />
            </section>
          )}
          <section className="card">
            <h2 className="section-title">Уровень по дисциплинам ФСП</h2>
            <p className="mt-1 text-sm text-ink-2">Нижняя граница уровня с учётом места, размера поля, разряда и давности результата.</p>
            <ul className="mt-5 space-y-4">
              {scores.map(ds => (
                <li key={ds.discipline}>
                  <div className="flex items-center justify-between text-sm"><span className="text-ink">{ds.label}</span>
                    <span className="flex items-center gap-2"><RankBadge rank={ds.best_rank} /><span className="num font-semibold text-ink">{ds.lcb.toFixed(2)}</span></span></div>
                  <div className="mt-2"><Meter value={Math.min(1, ds.lcb / 0.6)} /></div>
                </li>
              ))}
            </ul>
          </section>
          {creds.length > 0 && (
            <section className="card">
              <h2 className="section-title flex items-center gap-2"><Shield size={18} className="text-accent" aria-hidden />Проверяемые удостоверения</h2>
              <p className="mt-1 text-sm text-ink-2">Каждый результат подписан по стандарту W3C Verifiable Credentials 2.0. Попробуйте изменить место — проверка подписи не пройдёт.</p>
              <ul className="mt-4 divide-y divide-line">
                {creds.map((item: { id: string; valid: boolean; credential: { credentialSubject?: { achievement?: Achievement } } }) => {
                  const a = item.credential.credentialSubject?.achievement
                  return (
                    <li key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <div>
                        <p className="text-sm font-medium text-ink">{a?.eventName ?? item.id}</p>
                        <p className="text-xs text-ink-2">{a?.place != null && `${a.place} место из ${a.totalParticipants}`}{a?.rankEquivalent ? `, ${a.rankEquivalent}` : ''}{a?.teamSize && a.teamSize > 1 ? `, команда из ${a.teamSize}` : ''}</p>
                      </div>
                      <span className={item.valid ? 'badge-ok' : 'badge-warn'}>{item.valid ? 'подпись верна' : 'подпись не сходится'}</span>
                    </li>
                  )
                })}
              </ul>
              <button className="btn-secondary mt-4" onClick={() => {
                const copy = structuredClone(creds[0].credential)
                copy.credentialSubject.achievement.place = 999
                tamper.mutate(copy)
              }}>{tamper.isPending ? 'Проверяем…' : 'Подменить место и проверить подпись'}</button>
              {tamperNote && <p className="notice-error mt-3" role="status">{tamperNote}</p>}
            </section>
          )}
        </div>
      </div>
    </PublicShell>
  )
}
