import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2, Medal } from 'lucide-react'
import { apiError, fspAuthorize, updateMyProfile } from '../api/client'

interface Props { profile: { fsp_id: string | null; has_fsp: boolean; fsp_linked_at: string | null; results_count: number; birth_date?: string | null } }

/**
 * TZ 2.1: a candidate without FSP history is a normal case. The card says so plainly and offers to link
 * an FSP ID. Linking is an OpenID Connect login on the provider's page (Keycloak in production, a marked
 * demo page here): this site never sees the FSP password.
 */
export default function FspLinkCard({ profile }: Props) {
  const [error, setError] = useState('')
  const [born, setBorn] = useState('')
  const qc = useQueryClient()
  const saveDate = useMutation({
    mutationFn: () => updateMyProfile({ birth_date: born }),
    onSuccess: () => { setError(''); qc.invalidateQueries({ queryKey: ['myProfile'] }) },
    onError: (e: unknown) => setError(apiError(e, 'Дата не сохранена')),
  })
  const start = useMutation({
    mutationFn: () => fspAuthorize().then(r => r.data as { authorize_url: string }),
    onSuccess: data => window.location.assign(data.authorize_url),
    onError: (e: unknown) => setError(apiError(e, 'Не удалось начать привязку')),
  })

  if (profile.has_fsp) {
    return (
      <div className="card flex items-center gap-3 text-sm">
        <Medal className="text-accent shrink-0" size={20} />
        <p>ФСП ID <b>{profile.fsp_id}</b> привязан
          {profile.fsp_linked_at ? ` ${new Date(profile.fsp_linked_at).toLocaleDateString('ru-RU')}` : ''}.
          Результаты из протоколов: {profile.results_count}. Они показываются отдельно от грейда и подписаны удостоверениями.</p>
      </div>
    )
  }
  return (
    <div className="card space-y-3">
      <div className="flex items-start gap-3">
        <Link2 className="text-accent shrink-0 mt-0.5" size={20} />
        <div className="text-sm">
          <p className="section-title">Нет истории ФСП — это нормально</p>
          {!profile.birth_date && <p className="mb-2 text-ink">Чтобы работодатели вас видели, привяжите ФСП ID или укажите дату рождения.</p>}
          <p className="text-ink-2">Категория строится по опросу, заявленному грейду и тесту. Если вы участвовали
            в соревнованиях ФСП, войдите через ФСП ID: подтверждённые результаты добавятся в карточку.
            Пароль от ФСП вводится только на странице ФСП ID, этот сайт его не видит.</p>
        </div>
      </div>
      {!profile.birth_date && (
        <form className="flex flex-wrap items-end gap-2" onSubmit={e => { e.preventDefault(); if (born) saveDate.mutate() }}>
          <label className="text-sm text-ink-2" htmlFor="birth-date">Дата рождения
            <input id="birth-date" type="date" className="input mt-1" value={born} onChange={e => setBorn(e.target.value)} />
          </label>
          <button type="submit" className="btn-secondary text-sm" disabled={!born || saveDate.isPending}>Сохранить дату</button>
        </form>
      )}
      <button type="button" className="btn-primary text-sm" disabled={start.isPending} onClick={() => start.mutate()}>
        {start.isPending ? 'Открываем ФСП ID…' : 'Войти через ФСП ID'}
      </button>
      {error && <p className="notice-error" role="alert">{error}</p>}
    </div>
  )
}
