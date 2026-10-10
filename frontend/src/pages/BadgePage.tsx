import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { credentialStatus, issuerDid, verifyCredential } from '../api/client'
import PublicShell from '../components/PublicShell'
import { PageHeader } from '../components/ui'

interface Achievement {
  name?: string
  eventName?: string
  year?: number
  competitionStatus?: string
  bucket?: string
  discipline?: string
  place?: number
  totalParticipants?: number
}
interface Credential {
  type?: string[]
  credentialStatus?: { id?: string; type?: string }
  credentialSubject?: { achievement?: Achievement }
}

const STORED = 'fsp-badge'

function statusId(credential: Credential): string | null {
  const id = credential.credentialStatus?.id
  if (!id) return null
  try {
    const url = new URL(id, window.location.origin)
    if (url.origin !== window.location.origin) return null
    const marker = '/api/v1/public/credentials/'
    const at = url.pathname.indexOf(marker)
    if (at < 0 || !url.pathname.endsWith('/status')) return null
    return url.pathname.slice(at + '/api/v1'.length)
  } catch {
    return null
  }
}

/** Paste a credential or open the short card a candidate just asked for. */
export default function BadgePage() {
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const [claims, setClaims] = useState<Achievement | null>(null)
  const did = useQuery({ queryKey: ['issuerDid'], queryFn: () => issuerDid().then(r => r.data), retry: false })
  const check = useMutation({
    mutationFn: async (raw: string) => {
      const credential = JSON.parse(raw) as Credential
      const signed = await verifyCredential(credential).then(r => r.data as { valid: boolean })
      const path = statusId(credential)
      const status = path ? await credentialStatus(path.split('/').at(-2) || '').then(r => r.data as { revoked: boolean }).catch(() => null) : null
      return { credential, signed: signed.valid, status }
    },
    onSuccess: ({ credential, signed, status }) => {
      setClaims(credential.credentialSubject?.achievement ?? null)
      const kind = credential.type?.includes('OpenBadgeCredential') ? 'OpenBadgeCredential, ' : ''
      if (!signed) setNote(`${kind}подпись не сходится`.replace(/^, /, ''))
      else if (status?.revoked) setNote(`${kind}подпись сходится, удостоверение отозвано`)
      else if (status) setNote(`${kind}подпись сходится, удостоверение не отозвано`)
      else setNote(`${kind}подпись сходится. Это краткая карточка: названия события в ней нет, отдельной записи отзыва тоже.`)
    },
    onError: () => { setClaims(null); setNote('Это не удостоверение: нужен JSON, который выдала платформа.') },
  })

  useEffect(() => {
    const stored = sessionStorage.getItem(STORED)
    if (!stored) return
    sessionStorage.removeItem(STORED)
    setText(stored)
    check.mutate(stored)
    // The stored card is checked once, when the candidate opens this page from a result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const achievement = claims
  return (
    <PublicShell>
      <PageHeader
        title="Проверка удостоверения"
        lead="Подпись eddsa-jcs-2022. Полное удостоверение — OpenBadgeCredential со ссылкой на статус отзыва. Краткая карточка содержит год, статус соревнования и корзину места, без названия события и без имени."
      />
      {did.data?.id && (
        <p className="mb-4 text-sm text-ink-2">Ключ издателя: <span className="font-mono text-ink">{did.data.id}</span>. Тот же документ лежит в <span className="font-mono">/.well-known/did.json</span>.</p>
      )}
      <form className="card space-y-3 p-5" onSubmit={e => { e.preventDefault(); check.mutate(text) }}>
        <label className="block text-sm text-ink-2" htmlFor="badge-json">JSON удостоверения</label>
        <textarea id="badge-json" value={text} onChange={e => setText(e.target.value)} rows={8}
          className="input min-h-40 w-full font-mono text-xs" placeholder="{ … }" />
        <button className="btn-primary" type="submit" disabled={check.isPending || !text.trim()}>Проверить</button>
      </form>
      {note && <p className="mt-4 text-sm text-ink" role="status">{note}</p>}
      {achievement && (
        <dl className="card mt-4 grid gap-2 p-5 text-sm sm:grid-cols-2">
          <div><dt className="text-ink-3">Название</dt><dd className="text-ink">{achievement.eventName || achievement.name || '—'}</dd></div>
          <div><dt className="text-ink-3">Год</dt><dd className="num text-ink">{achievement.year ?? '—'}</dd></div>
          <div><dt className="text-ink-3">Статус</dt><dd className="text-ink">{achievement.competitionStatus ?? '—'}</dd></div>
          <div><dt className="text-ink-3">Место</dt><dd className="text-ink">{achievement.bucket ?? (achievement.place != null ? `${achievement.place} из ${achievement.totalParticipants}` : '—')}</dd></div>
          {achievement.discipline && <div><dt className="text-ink-3">Дисциплина</dt><dd className="text-ink">{achievement.discipline}</dd></div>}
        </dl>
      )}
    </PublicShell>
  )
}
