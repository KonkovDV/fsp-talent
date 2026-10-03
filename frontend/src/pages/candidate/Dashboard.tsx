import { useQuery } from '@tanstack/react-query'
import { getMyProfile, getMyOffers } from '../../api/client'
import GradeRadar from '../../components/GradeRadar'
import { roleRu } from '../../labels'
import { Trophy, Briefcase, Eye } from 'lucide-react'

const GRADE_CLASS: Record<string, string> = { lead: 'badge-lead', senior: 'badge-senior', middle: 'badge-middle', junior: 'badge-junior' }
const SOURCE: Record<string, string> = { declared: 'указан вами', experience: 'по опыту', default: 'опыт не указан' }

export default function CandidateDashboard() {
  const { data: profile, isLoading } = useQuery({ queryKey: ['myProfile'], queryFn: () => getMyProfile().then(r => r.data) })
  const { data: offers = [] } = useQuery({ queryKey: ['myOffers'], queryFn: () => getMyOffers().then(r => r.data) })

  if (isLoading) return <div className="animate-pulse h-64 bg-gray-100 rounded-2xl" />
  if (!profile) return null

  const pending = offers.filter((o: { status: string }) => o.status === 'pending').length
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-fsp-dark">Кабинет</h1>
      <div className="grid sm:grid-cols-3 gap-4">
        {[
          { icon: Trophy, label: 'Дисциплины ФСП', value: profile.discipline_scores?.length ?? 0 },
          { icon: Briefcase, label: 'Новые офферы', value: pending },
          { icon: Eye, label: 'В поиске', value: profile.discoverable ? 'да' : 'нет' },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-fsp-violet/10 flex items-center justify-center">
              <Icon size={20} className="text-fsp-violet" />
            </div>
            <div>
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-xl font-bold text-fsp-dark">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Подтверждено ФСП</h2>
            {profile.grade && <span className={GRADE_CLASS[profile.grade]}>{profile.grade}</span>}
          </div>
          <p className="text-xs text-gray-500 mb-2">Грейд {SOURCE[profile.grade_source] ?? profile.grade_source} и не выводится из результатов соревнований.</p>
          <GradeRadar scores={profile.discipline_scores ?? []} />
        </div>
        <div className="card">
          <h2 className="font-semibold mb-4">Навыки и роль</h2>
          <div className="flex flex-wrap gap-2">
            {(profile.stack ?? []).map((sk: string) => (
              <span key={sk} className="px-3 py-1 bg-fsp-violet/10 text-fsp-violet rounded-lg text-sm font-medium">{sk}</span>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100 space-y-1">
            <p className="text-sm text-gray-500">Роль: <span className="font-medium text-fsp-dark">{roleRu(profile.primary_role)}</span></p>
            <p className="text-sm text-gray-500">Регион: <span className="font-medium text-fsp-dark">{profile.region ?? '—'}</span></p>
            {(profile.explanation ?? []).map((line: string) => <p key={line} className="text-sm text-gray-500">{line}</p>)}
          </div>
          <div className="mt-4 space-y-1">
            {(profile.discipline_scores ?? []).map((ds: { discipline: string; label: string; lcb: number; best_rank: string | null }) => (
              <p key={ds.discipline} className="text-sm font-mono">
                {ds.label}: LCB {ds.lcb.toFixed(2)}{ds.best_rank ? ` · ${ds.best_rank}` : ''}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
