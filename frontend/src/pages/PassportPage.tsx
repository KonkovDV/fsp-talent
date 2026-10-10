import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getPublicPassport } from '../api/client'
import PublicShell from '../components/PublicShell'
import QrCode from '../components/QrCode'
import { Empty, PageHeader, Skeleton } from '../components/ui'
import { gradeRu } from '../labels'

/** What the QR opens. The server checks the signature and the revocation; the page only shows the answer. */
export default function PassportPage() {
  const { id } = useParams<{ id: string }>()
  const query = useQuery({
    queryKey: ['public-passport', id],
    queryFn: () => getPublicPassport(id!).then(r => r.data),
    retry: false,
  })
  if (query.isError) {
    return <PublicShell><Empty title="Паспорта нет" action={<Link to="/badge" className="btn-secondary">Проверить удостоверение</Link>}>
      Ссылка неверна или владелец удалил профиль.</Empty></PublicShell>
  }
  if (!query.data) return <PublicShell><Skeleton className="h-96" /></PublicShell>
  const { valid, signature, revoked, issued_at, credential } = query.data
  const claims = credential.credentialSubject?.achievement
  const verdict = revoked ? 'Паспорт отозван владельцем' : valid ? 'Подпись платформы верна' : 'Подпись не сходится'
  return (
    <PublicShell>
      <PageHeader title="Паспорт навыков" lead="Подпись Ed25519 (eddsa-jcs-2022). Имени, контактов и названий соревнований в паспорте нет." />
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_220px]">
        <div className="space-y-4">
          <p role="status" data-testid="passport-verdict"
            className={valid ? 'badge-ok w-max' : 'badge-warn w-max'}>{verdict}</p>
          {issued_at && <p className="text-sm text-ink-2">Выпущен {new Date(issued_at).toLocaleDateString('ru-RU')}{!signature && ', документ изменён после подписи'}</p>}
          {claims && !revoked && (
            <>
              <section className="card">
                <h2 className="section-title">Грейды, подтверждённые тестом</h2>
                {claims.grades.length ? (
                  <ul className="mt-2 space-y-1 text-sm">
                    {claims.grades.map(g => <li key={g.specialization}><span className="text-ink">{g.specialization}</span>: {gradeRu(g.grade)}, {new Date(g.confirmedOn).toLocaleDateString('ru-RU')}</li>)}
                  </ul>
                ) : <p className="mt-2 text-sm text-ink-2">Тест ещё не пройден.</p>}
              </section>
              {claims.testedSkills.length > 0 && (
                <section className="card">
                  <h2 className="section-title">Навыки, подтверждённые тестом</h2>
                  <ul className="mt-2 flex flex-wrap gap-2">{claims.testedSkills.map(s => <li key={s} className="badge-ok">{s}</li>)}</ul>
                </section>
              )}
              {claims.fspResults.length > 0 && (
                <section className="card">
                  <h2 className="section-title">Результаты ФСП</h2>
                  <ul className="mt-2 space-y-1 text-sm">
                    {claims.fspResults.map(r => (
                      <li key={r.discipline}><span className="text-ink">{r.discipline}</span>: {r.results} в протоколах, лучшее — {r.bestBucket}, {r.statuses.join(', ')}, последний — {r.lastYear}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
        <aside className="card flex flex-col items-center gap-2">
          <QrCode value={window.location.href} label="QR-код этой страницы" />
          <p className="text-center text-xs text-ink-3">Отсканируйте, чтобы открыть паспорт на другом устройстве.</p>
        </aside>
      </div>
    </PublicShell>
  )
}
