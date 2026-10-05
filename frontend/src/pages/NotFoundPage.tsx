import { Link } from 'react-router-dom'
import PublicShell from '../components/PublicShell'

export default function NotFoundPage() {
  return (
    <PublicShell>
      <div className="mx-auto max-w-md py-16 text-center">
        <p className="font-display text-6xl font-semibold text-ink-3">404</p>
        <h1 className="mt-4 font-display text-2xl font-semibold text-ink">Такой страницы нет</h1>
        <p className="mt-2 text-ink-2">Возможно, ссылка устарела. Начните с главной или войдите в кабинет.</p>
        <div className="mt-6 flex justify-center gap-3"><Link to="/" className="btn-primary">На главную</Link><Link to="/login" className="btn-secondary">Войти</Link></div>
      </div>
    </PublicShell>
  )
}
