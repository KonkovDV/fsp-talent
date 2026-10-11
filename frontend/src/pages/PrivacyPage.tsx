import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { legalDocument } from '../api/client'
import PublicShell from '../components/PublicShell'
import DemoStandNotice from '../components/DemoStandNotice'
import { PageHeader, Skeleton } from '../components/ui'

/** **bold** inside a line of the policy; the text is ours (app/legal/docs), so no HTML is ever injected. */
function inline(line: string): ReactNode {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i} className="font-semibold text-ink">{part.slice(2, -2)}</strong>
      : <Fragment key={i}>{part}</Fragment>)
}

/**
 * The privacy policy (152-FZ art. 18.1 part 2), served by the same public endpoint as the consents,
 * so the page, /legal and the API always show one text with one version and SHA-256.
 */
export default function PrivacyPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['legal', 'privacy_policy'], queryFn: () => legalDocument('privacy_policy').then(r => r.data),
  })
  const paragraphs = (data?.body_md ?? '').replace(/^# .*\n+/, '').split(/\n{2,}/).filter(Boolean)
  return (
    <PublicShell>
      <PageHeader title={data?.title ?? 'Политика обработки персональных данных'}
        lead="Как платформа обращается с персональными данными. Это не согласие — принимать её не нужно; согласия лежат в разделе «Документы и согласия»." />
      <DemoStandNotice className="mb-4" />
      {isLoading && <Skeleton className="h-64" />}
      {isError && <p className="notice-error" role="alert">Не удалось загрузить политику. Обновите страницу.</p>}
      {data && (
        <article className="card space-y-3 text-sm leading-relaxed text-ink-2" data-testid="privacy-policy">
          {paragraphs.map((p, i) => (
            <p key={i}>{p.split('\n').map((line, j) => <Fragment key={j}>{j > 0 && <br />}{inline(line)}</Fragment>)}</p>
          ))}
          <p className="font-mono text-xs text-ink-3">версия {data.version}, SHA-256 {data.sha256.slice(0, 16)}…</p>
        </article>
      )}
      <p className="mt-4 text-sm text-ink-2">
        <Link to="/legal" className="text-accent underline">Документы и согласия</Link>
      </p>
    </PublicShell>
  )
}
