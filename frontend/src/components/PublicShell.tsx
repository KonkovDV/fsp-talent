import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { Brand } from './Brand'
import { SiteFooter, ThemeToggle } from './Layout'

/** Header and footer for pages open without an account: home, rating, public profile, 404. */
export function PublicHeader() {
  const role = useAuthStore(s => s.userRole)
  return (
    <header className="border-b border-line bg-panel">
      <div className="brand-stripe" aria-hidden />
      <div className="mx-auto flex h-16 max-w-page items-center justify-between gap-4 px-4 sm:px-6">
        <Brand />
        <nav className="flex items-center gap-1" aria-label="Главное меню">
          <Link to="/leaderboard" className="btn-nav hidden sm:inline-flex">Рейтинг</Link>
          <ThemeToggle />
          {role ? <Link to={role === 'participant' ? '/candidate' : '/employer'} className="btn-primary btn-sm">Мой кабинет</Link> : <>
            <Link to="/login" className="btn-nav">Войти</Link>
            <Link to="/register?role=employer" className="btn-primary btn-sm hidden sm:inline-flex">Найти кандидата</Link>
          </>}
        </nav>
      </div>
    </header>
  )
}

export default function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <PublicHeader />
      <main id="main" className="mx-auto w-full max-w-page flex-1 px-4 py-10 sm:px-6">{children}</main>
      <SiteFooter />
    </div>
  )
}
