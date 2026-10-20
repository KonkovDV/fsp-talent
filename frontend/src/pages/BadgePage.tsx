import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { issuerDid, verifyCredential } from '../api/client'
import PublicShell from '../components/PublicShell'
import QrCode from '../components/QrCode'
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
interface StatusEntry {
  id?: string
  type?: string
}
interface Credential {
  type?: string[]
  credentialStatus?: StatusEntry | StatusEntry[]
  credentialSubject?: { achievement?: Achievement }
}
interface Checked {
  valid?: boolean
  signature?: boolean
  revoked?: boolean
}

const STORED = 'fsp-badge'

/** VC 2.0 allows one status entry or a list: a full credential carries its own link and a W3C status-list entry. */
function statusEntries(credential: Credential): StatusEntry[] {
  const status = credential.credentialStatus
  return Array.isArray(status) ? status : status ? [status] : []
}

/** Paste a credential or open the short card a candidate just asked for. */
export default function BadgePage() {
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  // A broken signature or a non-credential is an error: nothing from such a document is shown as a fact.
  const [failed, setFailed] = useState(false)
  const [claims, setClaims] = useState<Achievement | null>(null)
  const did = useQuery({ queryKey: ['issuerDid'], queryFn: () => issuerDid().then(r => r.data), retry: false })
  const check = useMutation({
    mutationFn: async (raw: string) => {
      const credential = JSON.parse(raw) as Credential
      const checked = await verifyCredential(credential).then(r => r.data as Checked)
      // The server reads the revocation row itself: a revoked credential still has a valid signature.
      const signed = checked.signature ?? Boolean(checked.valid)
      return { credential, signed, revoked: Boolean(checked.revoked), entries: statusEntries(credential) }
    },
    onSuccess: ({ credential, signed, revoked, entries }) => {
      setFailed(!signed)
      setClaims(signed && !revoked ? credential.credentialSubject?.achievement ?? null : null)
      const kind = credential.type?.includes('OpenBadgeCredential') ? 'OpenBadgeCredential, ' : ''
      const listed = entries.some(e => e.type === 'BitstringStatusListEntry')
      if (!signed) setNote(`${kind}подпись не сходится: документ изменён или выдан не этой платформой. Данные из него не показываем.`.replace(/^, /, ''))
      else if (revoked) setNote(`${kind}подпись сходится, но владелец отозвал удостоверение. Данные из него не показываем.`)
      else if (entries.length) setNote(`${kind}подпись сходится, удостоверение не отозвано.${listed ? ' Статус опубликован и в открытом списке W3C Bitstring Status List.' : ''}`)
      else setNote(`${kind}подпись сходится. Это краткая карточка: названия события в ней нет, отдельной записи отзыва тоже.`)
    },
    onError: () => { setClaims(null); setFailed(true); setNote('Это не удостоверение: нужен JSON, который выдала платформа.') },
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
      <div className="mb-4 flex flex-wrap items-center gap-4">
        <QrCode value={`${window.location.origin}/.well-known/did.json`} label="QR-код документа ключа издателя" />
        <p className="max-w-prose text-sm text-ink-2">
          {did.data?.id ? <>Ключ издателя: <span className="font-mono text-ink">{did.data.id}</span>. </> : null}
          Код открывает <span className="font-mono">/.well-known/did.json</span> на этом сайте. Имени в документе нет.
        </p>
      </div>
      <form className="card space-y-3 p-5" onSubmit={e => { e.preventDefault(); check.mutate(text) }}>
        <label className="block text-sm text-ink-2" htmlFor="badge-json">JSON удостоверения</label>
        <textarea id="badge-json" value={text} onChange={e => { setText(e.target.value); setNote(''); setClaims(null); setFailed(false) }} rows={8}
          className="input min-h-40 w-full font-mono text-xs" placeholder="{ … }" />
        <button className="btn-primary" type="submit" disabled={check.isPending || !text.trim()}>Проверить</button>
      </form>
      {note && (failed
        ? <p className="notice-error mt-4" role="alert">{note}</p>
        : <p className="mt-4 text-sm text-ink" role="status">{note}</p>)}
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
