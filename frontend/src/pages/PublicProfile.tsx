import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { getPublicProfile, getCredentials, verifyCredential } from '../api/client'
import GradeRadar from '../components/GradeRadar'
import { roleRu } from '../labels'
import { Shield, ArrowLeft } from 'lucide-react'

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
    return (
      <div className="min-h-screen flex items-center justify-center bg-fsp-light-bg">
        <div className="card text-center space-y-3">
          <p>Публичный профиль не найден. Его включают только совершеннолетние.</p>
          <Link to="/leaderboard" className="text-fsp-violet text-sm">К лидерборду</Link>
        </div>
      </div>
    )
  }
  if (!profileQuery.data) {
    return <div className="min-h-screen flex items-center justify-center"><div className="animate-pulse h-64 w-96 bg-gray-100 rounded-2xl" /></div>
  }
  const profile = profileQuery.data
  return (
    <div className="min-h-screen bg-fsp-light-bg">
      <header className="bg-fsp-dark text-white py-4">
        <div className="max-w-5xl mx-auto px-6 flex items-center gap-3">
          <Link to="/leaderboard" className="text-gray-400 hover:text-white"><ArrowLeft size={18} /></Link>
          <span className="text-xl font-bold text-fsp-violet">FSP Talent</span>
        </div>
      </header>
      <div className="max-w-5xl mx-auto px-6 py-10 grid md:grid-cols-3 gap-6">
        <div className="md:col-span-1 space-y-4">
          <div className="card text-center">
            <div className="w-16 h-16 rounded-full bg-fsp-violet/20 flex items-center justify-center text-fsp-violet text-2xl font-bold mx-auto mb-3">
              {(profile.display_name ?? 'У')[0]}
            </div>
            <h1 className="text-lg font-bold">{profile.display_name}</h1>
            <p className="text-sm text-text-muted mt-1">{profile.region}</p>
            <div className="mt-3">
              <span className="badge bg-fsp-violet/10 text-fsp-violet">{roleRu(profile.primary_role)}</span>{' '}
              <span className="badge bg-gray-100 text-gray-700">{profile.grade}</span>
            </div>
          </div>
          <div className="card">
            <h3 className="text-sm font-semibold mb-2">Навыки</h3>
            <div className="flex flex-wrap gap-1.5">
              {(profile.skills ?? []).map((skill: string) => (
                <span key={skill} className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs">{skill}</span>
              ))}
            </div>
          </div>
        </div>
        <div className="md:col-span-2 space-y-4">
          <div className="card">
            <h2 className="font-semibold mb-1">Уровень по дисциплинам ФСП</h2>
            <p className="text-xs text-text-muted mb-3">График — средний уровень после сжатия. Ранжирование идёт по нижней границе.</p>
            <GradeRadar scores={profile.discipline_scores ?? []} />
            <div className="mt-3 space-y-1">
              {(profile.discipline_scores ?? []).map((ds: { discipline: string; label: string; lcb: number; best_rank: string | null }) => (
                <p key={ds.discipline} className="text-sm font-mono">{ds.label}: LCB {ds.lcb.toFixed(2)}{ds.best_rank ? ` · ${ds.best_rank}` : ''}</p>
              ))}
            </div>
          </div>
          {creds.length > 0 && (
            <div className="card">
              <h2 className="font-semibold mb-3 flex items-center gap-2"><Shield size={16} className="text-fsp-violet" />Проверяемые удостоверения</h2>
              <div className="space-y-3">
                {creds.map((item: { id: string; valid: boolean; issued_at: string; credential: { credentialSubject?: { achievement?: Achievement } } }) => {
                  const achievement = item.credential.credentialSubject?.achievement
                  return (
                    <div key={item.id} className="bg-gray-50 rounded-xl p-3 space-y-1">
                      <p className="text-sm font-medium">{achievement?.eventName ?? item.id}</p>
                      <p className="text-xs text-gray-600">
                        {achievement?.place != null && `${achievement.place} место из ${achievement.totalParticipants}`}
                        {achievement?.rankEquivalent ? ` · ${achievement.rankEquivalent}` : ''}
                        {achievement?.teamSize && achievement.teamSize > 1 ? ` · команда ${achievement.teamSize}` : ''}
                        {achievement?.eventDate ? ` · ${achievement.eventDate}` : ''}
                      </p>
                      <p className="text-xs">{item.valid ? 'подпись верна' : 'подпись не сходится'}</p>
                    </div>
                  )
                })}
              </div>
              <button
                className="btn-secondary text-sm mt-4"
                onClick={() => {
                  const copy = structuredClone(creds[0].credential)
                  copy.credentialSubject.achievement.place = 999
                  tamper.mutate(copy)
                }}
              >
                {tamper.isPending ? 'Проверяем…' : 'Подменить место и проверить'}
              </button>
              {tamperNote && <p className="text-sm text-fsp-red mt-2">{tamperNote}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
