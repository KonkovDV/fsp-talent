import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { legalDocuments, legalProcessor, type LegalDoc } from '../api/client'
import PublicShell from '../components/PublicShell'
import { LegalDocModal } from '../components/LegalConsents'
import DemoStandNotice from '../components/DemoStandNotice'
import { PageHeader, Skeleton } from '../components/ui'

/** Every legal text the platform asks people to accept, with version and SHA-256 of the exact wording. */
export default function LegalPage() {
  const [open, setOpen] = useState<string | null>(null)
  const { data: docs = [], isLoading } = useQuery<LegalDoc[]>({ queryKey: ['legal-all'], queryFn: () => legalDocuments().then(r => r.data) })
  const { data: processor } = useQuery({ queryKey: ['legal-processor'], queryFn: () => legalProcessor().then(r => r.data) })
  return (
    <PublicShell>
      <PageHeader title="Документы и согласия"
        lead="Согласие на обработку персональных данных — отдельный документ, как требует 152-ФЗ. В профиле видно, какую версию вы приняли, и любое согласие можно отозвать." />
      <DemoStandNotice className="mb-4" withPolicyLink />
      {isLoading && <Skeleton className="h-48" />}
      <div className="card overflow-x-auto p-0" tabIndex={0} role="region" aria-label="Таблица документов">
        <table className="protocol">
          <thead><tr><th>Документ</th><th>Для кого</th><th>Версия</th><th>SHA-256</th></tr></thead>
          <tbody>
            {docs.map(d => (
              <tr key={d.kind}>
                <td><button onClick={() => setOpen(d.kind)} className="text-left font-medium text-accent hover:underline">{d.title}</button>
                  {d.consent === false
                    ? <span className="block text-xs text-ink-3">для ознакомления, принимать не нужно</span>
                    : !d.required && <span className="block text-xs text-ink-3">по желанию</span>}</td>
                <td className="text-ink-2">{d.roles.map(r => (r === 'participant' ? 'кандидат' : 'работодатель')).join(', ')}</td>
                <td className="num text-ink-2">{d.version}</td>
                <td className="font-mono text-xs text-ink-3">{d.sha256.slice(0, 16)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card mt-4 space-y-2 text-sm text-ink-2">
        <p><span className="font-medium text-ink">Оператор.</span> Демонстрационный стенд: команда-участник хакатона «Лидеры цифровой трансформации — 2026». В промышленном контуре оператор — ФСП или владелец платформы; наименование, ОГРН/ИНН и адрес публикуются до запуска. Подробно — в <Link to="/privacy" className="text-accent underline">политике обработки персональных данных</Link>.</p>
        <p data-testid="processor"><span className="font-medium text-ink">Помощник на основе модели.</span>{' '}
          {processor?.enabled
            ? `Сейчас обработчик — ${processor.label}; серверы в Российской Федерации, резюме передаётся без имени и контактов.`
            : 'Сейчас выключен: резюме за пределы платформы не передаётся.'}</p>
      </div>
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </PublicShell>
  )
}
