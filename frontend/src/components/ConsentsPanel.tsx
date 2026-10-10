import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { apiError, myConsents, withdrawConsent } from '../api/client'
import { LegalDocModal } from './LegalConsents'

interface Effect { code: string; text: string }
interface ConsentRow {
  kind: string; title: string; version: string; required: boolean; active: boolean
  given_at: string | null; accepted_version: string | null; outdated: boolean
  if_withdrawn?: Effect[]
}

/** The person's consents with the exact version accepted; any of them can be withdrawn here. */
export default function ConsentsPanel() {
  const qc = useQueryClient()
  const [open, setOpen] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const { data = [] } = useQuery<ConsentRow[]>({ queryKey: ['myConsents'], queryFn: () => myConsents().then(r => r.data) })
  const withdraw = useMutation({
    mutationFn: (kind: string) => withdrawConsent(kind).then(r => r.data),
    onSuccess: (res: { effects?: string[]; effect_items?: Effect[] }) => {
      const lines = res.effect_items?.map(item => item.text) ?? res.effects ?? []
      setNote(lines.join(' ') || 'Согласие отозвано')
      qc.invalidateQueries({ queryKey: ['myConsents'] }); qc.invalidateQueries({ queryKey: ['myProfile'] })
    },
    onError: (e: unknown) => setNote(apiError(e)),
  })
  return (
    <div className="card space-y-3">
      <h2 className="section-title flex items-center gap-2"><ShieldCheck size={18} className="text-accent" />Согласия</h2>
      <ul className="divide-y divide-line text-sm">
        {data.map(row => (
          <li key={row.kind} className="py-2 flex flex-wrap items-center gap-2 justify-between">
            <button onClick={() => setOpen(row.kind)} className="text-left hover:underline">{row.title}</button>
            <span className="text-ink-3 text-xs">
              {row.active
                ? `дано ${new Date(row.given_at!).toLocaleDateString('ru-RU')}, версия ${row.accepted_version}${row.outdated ? ' (текст обновлён)' : ''}`
                : 'не дано'}
            </span>
            {row.active && (
              <button onClick={() => {
                const lines = (row.if_withdrawn ?? []).map(item => item.text).join('\n')
                if (window.confirm(lines || 'Отозвать согласие?')) withdraw.mutate(row.kind)
              }} className="inline-flex min-h-6 items-center text-xs font-medium text-danger hover:underline">Отозвать</button>
            )}
          </li>
        ))}
      </ul>
      {note && <p className="text-sm text-ink-2" role="status">{note}</p>}
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
