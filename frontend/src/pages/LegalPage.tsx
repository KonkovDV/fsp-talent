import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { legalDocuments, legalProcessor, type LegalDoc } from '../api/client'
import PublicShell from '../components/PublicShell'
import { LegalDocModal } from '../components/LegalConsents'
import DemoStandNotice from '../components/DemoStandNotice'
import { PageHeader, Skeleton } from '../components/ui'

function roleLabel(roles: string[]): string {
  return roles.map(r => (r === 'participant' ? 'кандидат' : 'работодатель')).join(', ')
}

function DocMeta({ d }: { d: LegalDoc }) {
  if (d.consent === false) return <span className="block text-xs text-ink-3">для ознакомления, принимать не нужно</span>
  if (!d.required) return <span className="block text-xs text-ink-3">по желанию</span>
  return null
}

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
      {docs.length > 0 && (
        <>
          <ul className="space-y-3 sm:hidden" aria-label="Список документов">
            {docs.map(d => (
              <li key={d.kind} className="card space-y-1.5">
                <button type="button" onClick={() => setOpen(d.kind)} className="text-left font-medium text-accent hover:underline">{d.title}</button>
                <DocMeta d={d} />
                <p className="text-sm text-ink-2">{roleLabel(d.roles)} · версия {d.version}</p>
                <p className="break-all font-mono text-[11px] leading-snug text-ink-3" style={{ overflowWrap: 'anywhere' }}>
                  SHA-256 {d.sha256}
                </p>
              </li>
            ))}
          </ul>
          <div className="card hidden w-0 min-w-full overflow-x-auto p-0 sm:block" tabIndex={0} role="region" aria-label="Таблица документов">
            <table className="protocol w-full table-fixed">
              <thead><tr>
                <th className="w-[36%]">Документ</th>
                <th className="w-[18%]">Для кого</th>
                <th className="w-[12%]">Версия</th>
                <th className="w-[34%]">SHA-256</th>
              </tr></thead>
              <tbody>
                {docs.map(d => (
                  <tr key={d.kind}>
                    <td>
                      <button type="button" onClick={() => setOpen(d.kind)} className="text-left font-medium text-accent hover:underline">{d.title}</button>
                      <DocMeta d={d} />
                    </td>
                    <td className="text-ink-2">{roleLabel(d.roles)}</td>
                    <td className="num text-ink-2">{d.version}</td>
                    <td className="break-all font-mono text-[11px] leading-snug text-ink-3" style={{ overflowWrap: 'anywhere' }}>
                      {d.sha256}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="card mt-4 space-y-2 text-sm text-ink-2">
        <p><span className="font-medium text-ink">Оператор.</span> Демонстрационный стенд: команда проекта «ФСП Талант». Проект самостоятельный, лицензия MIT. В промышленном контуре оператор — ФСП или владелец платформы; наименование, ОГРН/ИНН и адрес публикуются до запуска. Подробно — в <Link to="/privacy" className="text-accent underline">политике обработки персональных данных</Link>.</p>
        <p data-testid="processor"><span className="font-medium text-ink">Помощник на основе модели.</span>{' '}
          {processor?.enabled
            ? `Сейчас обработчик — ${processor.label}; серверы в Российской Федерации, резюме передаётся без имени и контактов.`
            : 'Сейчас выключен: резюме за пределы платформы не передаётся.'}</p>
      </div>
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </PublicShell>
  )
}
