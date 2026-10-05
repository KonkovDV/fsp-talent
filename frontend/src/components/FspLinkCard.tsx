import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2, Medal } from 'lucide-react'
import { apiError, linkFsp } from '../api/client'

interface Props { profile: { fsp_id: string | null; has_fsp: boolean; fsp_linked_at: string | null; results_count: number } }

/**
 * TZ 2.1: a candidate without FSP history is a normal case. The card says so plainly and offers to link
 * an FSP account. In production the form is replaced by "Войти через ФСП ID" (Keycloak, OIDC).
 */
export default function FspLinkCard({ profile }: Props) {
  const qc = useQueryClient()
  const [fspId, setFspId] = useState('')
  const [secret, setSecret] = useState('')
  const [message, setMessage] = useState('')
  const link = useMutation({
    mutationFn: () => linkFsp(fspId.trim(), secret).then(r => r.data),
    onSuccess: (data) => {
      setMessage(`Привязано: ${data.fsp_id}, протоколов: ${data.results}`)
      qc.invalidateQueries({ queryKey: ['myProfile'] })
    },
    onError: (e: unknown) => setMessage(apiError(e, 'Не удалось привязать')),
  })

  if (profile.has_fsp) {
    return (
      <div className="card flex items-center gap-3 text-sm">
        <Medal className="text-fsp-violet shrink-0" size={20} />
        <p>ФСП ID <b>{profile.fsp_id}</b> привязан
          {profile.fsp_linked_at ? ` ${new Date(profile.fsp_linked_at).toLocaleDateString('ru-RU')}` : ''}.
          Результаты из протоколов: {profile.results_count}. Они показываются отдельно от грейда и подписаны удостоверениями.</p>
      </div>
    )
  }
  return (
    <div className="card space-y-3">
      <div className="flex items-start gap-3">
        <Link2 className="text-fsp-violet shrink-0 mt-0.5" size={20} />
        <div className="text-sm">
          <p className="font-semibold">Нет истории ФСП — это нормально</p>
          <p className="text-text-secondary">Категория строится по опросу, заявленному грейду и тесту. Если вы участвовали
            в соревнованиях ФСП, привяжите аккаунт: подтверждённые результаты добавятся в карточку.</p>
        </div>
      </div>
      <form className="grid sm:grid-cols-[1fr_1fr_auto] gap-2" onSubmit={e => { e.preventDefault(); link.mutate() }}>
        <input value={fspId} onChange={e => setFspId(e.target.value)} placeholder="ФСП ID" aria-label="ФСП ID" className="input" />
        <input value={secret} onChange={e => setSecret(e.target.value)} type="password" placeholder="Пароль ФСП"
          aria-label="Пароль ФСП" className="input" />
        <button disabled={!fspId || !secret || link.isPending} className="btn-primary text-sm">Привязать</button>
      </form>
      <p className="text-xs text-text-muted">Демо-мок: FSP2000–FSP2099, пароль test. В продакшене — вход через ФСП ID (Keycloak).</p>
      {message && <p className="text-sm" role="status">{message}</p>}
    </div>
  )
}
