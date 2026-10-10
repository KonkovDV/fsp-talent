import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { Brand } from './Brand'
import { MobileMenu, SiteFooter, ThemeToggle, type NavItem } from './chrome'

const PUBLIC_LINKS: NavItem[] = [
  { to: '/method', label: 'Как устроен тест' },
  { to: '/leaderboard', label: 'Рейтинг' },
  { to: '/badge', label: 'Удостоверение' },
  { to: '/jury', label: 'Жюри' },
]

/** Header and footer for pages open without an account: home, rating, public profile, 404. */
export function PublicHeader({ onBrand = false }: { onBrand?: boolean }) {
  const role = useAuthStore(s => s.userRole)
  return (
    <header className={onBrand ? 'bg-panel' : 'border-b border-line bg-panel'}>
      <div className="brand-stripe" aria-hidden />
      <div className="mx-auto flex h-14 max-w-page items-center justify-between gap-3 px-4 sm:h-16 sm:px-6">
        <Brand />
        <nav className="flex items-center gap-1" aria-label="Главное меню">
          <ul className="mr-1 hidden items-center gap-0.5 md:flex">
            {PUBLIC_LINKS.map(l => (
              <li key={l.to}>
                <NavLink to={l.to} className={({ isActive }) => `btn-nav ${isActive ? 'bg-sunken text-ink' : ''}`}>{l.label}</NavLink>
              </li>
            ))}
          </ul>
          <span className="hidden md:inline-flex"><ThemeToggle /></span>
          {role ? <Link to={role === 'participant' ? '/candidate' : '/employer'} className="btn-primary btn-sm">Мой кабинет</Link> : <>
            <Link to="/login" className="btn-nav">Войти</Link>
            <Link to="/register?role=employer" className="btn-primary btn-sm hidden sm:inline-flex">Найти кандидата</Link>
          </>}
          <MobileMenu links={[{ to: '/', label: 'Главная', end: true }, ...PUBLIC_LINKS]} label="Меню" />
        </nav>
      </div>
    </header>
  )
}

export default function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <PublicHeader />
      <main id="main" className="mx-auto w-full max-w-page flex-1 px-4 py-8 sm:px-6 sm:py-12">{children}</main>
      <SiteFooter />
    </div>
  )
}
