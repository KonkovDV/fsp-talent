import { Link } from 'react-router-dom'
import PublicShell from '../components/PublicShell'
import { PageHeader } from '../components/ui'

/** Three ways in for a jury: two demo accounts and the public pages. No third login. */
export default function JuryPage() {
  return (
    <PublicShell>
      <PageHeader
        title="Режим жюри"
        lead="Отдельного входа для жюри нет. Кандидат и работодатель — демо-аккаунты, пароль demo12345. Публичные страницы открываются без аккаунта."
      />
      <div className="grid gap-4 md:grid-cols-3">
        <section className="card p-5">
          <h2 className="font-display text-lg font-bold text-ink">Кандидат</h2>
          <p className="mt-2 text-sm text-ink-2">Профиль с историей ФСП, тест и приглашения.</p>
          <p className="mt-3 font-mono text-sm text-ink">fsp001@demo.talent</p>
          <Link to="/login" className="btn-primary mt-4 inline-flex">Войти как кандидат</Link>
        </section>
        <section className="card p-5">
          <h2 className="font-display text-lg font-bold text-ink">Работодатель</h2>
          <p className="mt-2 text-sm text-ink-2">Компания «Сибирский код»: потребности, подборка, задания.</p>
          <p className="mt-3 font-mono text-sm text-ink">hr@sibcode.demo</p>
          <Link to="/login?role=employer" className="btn-primary mt-4 inline-flex">Войти как работодатель</Link>
        </section>
        <section className="card p-5">
          <h2 className="font-display text-lg font-bold text-ink">Без аккаунта</h2>
          <p className="mt-2 text-sm text-ink-2">Методика теста и проверка удостоверения. Это третья сторона просмотра.</p>
          <div className="mt-4 flex flex-col items-start gap-2">
            <Link to="/method" className="text-sm text-accent underline">Как устроен тест</Link>
            <Link to="/badge" className="text-sm text-accent underline">Проверка удостоверения</Link>
          </div>
        </section>
      </div>
      <p className="mt-6 text-sm text-ink-2">
        Набор этих профилей в JSON и CSV проверяется при запуске стенда и в базу не записывается.
      </p>
    </PublicShell>
  )
}
