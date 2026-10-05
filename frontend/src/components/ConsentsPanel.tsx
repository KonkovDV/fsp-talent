import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { apiError, myConsents, withdrawConsent } from '../api/client'
import { LegalDocModal } from './LegalConsents'

interface ConsentRow {
  kind: string; title: string; version: string; required: boolean; active: boolean
  given_at: string | null; accepted_version: string | null; outdated: boolean
}

/** The person's consents with the exact version accepted; any of them can be withdrawn here. */
export default function ConsentsPanel() {
  const qc = useQueryClient()
  const [open, setOpen] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const { data = [] } = useQuery<ConsentRow[]>({ queryKey: ['myConsents'], queryFn: () => myConsents().then(r => r.data) })
  const withdraw = useMutation({
    mutationFn: (kind: string) => withdrawConsent(kind).then(r => r.data),
    onSuccess: (res: { effects: string[] }) => {
      setNote(res.effects.join('. ') || 'Согласие отозвано')
      qc.invalidateQueries({ queryKey: ['myConsents'] }); qc.invalidateQueries({ queryKey: ['myProfile'] })
    },
    onError: (e: unknown) => setNote(apiError(e)),
  })
  return (
    <div className="card space-y-3">
      <h2 className="font-semibold flex items-center gap-2"><ShieldCheck size={18} className="text-fsp-violet" />Согласия</h2>
      <ul className="divide-y divide-gray-100 text-sm">
        {data.map(row => (
          <li key={row.kind} className="py-2 flex flex-wrap items-center gap-2 justify-between">
            <button onClick={() => setOpen(row.kind)} className="text-left hover:underline">{row.title}</button>
            <span className="text-text-muted text-xs">
              {row.active
                ? `дано ${new Date(row.given_at!).toLocaleDateString('ru-RU')}, версия ${row.accepted_version}${row.outdated ? ' (текст обновлён)' : ''}`
                : 'не дано'}
            </span>
            {row.active && (
              <button onClick={() => {
                if (!row.required || window.confirm('Без этого согласия карточка будет скрыта, а данные удалены в течение 30 дней. Отозвать?'))
                  withdraw.mutate(row.kind)
              }} className="text-xs text-fsp-red hover:underline">Отозвать</button>
            )}
          </li>
        ))}
      </ul>
      {note && <p className="text-sm text-text-secondary" role="status">{note}</p>}
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
