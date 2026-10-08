import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { legalDocuments, type LegalDoc } from '../api/client'
import PublicShell from '../components/PublicShell'
import { LegalDocModal } from '../components/LegalConsents'
import { PageHeader, Skeleton } from '../components/ui'

/** Every legal text the platform asks people to accept, with version and SHA-256 of the exact wording. */
export default function LegalPage() {
  const [open, setOpen] = useState<string | null>(null)
  const { data: docs = [], isLoading } = useQuery<LegalDoc[]>({ queryKey: ['legal-all'], queryFn: () => legalDocuments().then(r => r.data) })
  return (
    <PublicShell>
      <PageHeader title="Документы и согласия"
        lead="Согласие на обработку персональных данных — отдельный документ, как требует 152-ФЗ. В профиле видно, какую версию вы приняли, и любое согласие можно отозвать." />
      {isLoading && <Skeleton className="h-48" />}
      <div className="card overflow-x-auto p-0" tabIndex={0} role="region" aria-label="Таблица документов">
        <table className="protocol">
          <thead><tr><th>Документ</th><th>Для кого</th><th>Версия</th><th>SHA-256</th></tr></thead>
          <tbody>
            {docs.map(d => (
              <tr key={d.kind}>
                <td><button onClick={() => setOpen(d.kind)} className="text-left font-medium text-accent hover:underline">{d.title}</button>
                  {!d.required && <span className="block text-xs text-ink-3">по желанию</span>}</td>
                <td className="text-ink-2">{d.roles.map(r => (r === 'participant' ? 'кандидат' : 'работодатель')).join(', ')}</td>
                <td className="num text-ink-2">{d.version}</td>
                <td className="font-mono text-xs text-ink-3">{d.sha256.slice(0, 16)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </PublicShell>
  )
}
