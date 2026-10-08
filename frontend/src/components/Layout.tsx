import { useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { LogOut, Menu, Moon, Sun, X } from 'lucide-react'
import { signOut } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { useTheme } from '../lib/theme'
import { Brand } from './Brand'
import Modal from './Modal'
import NotificationBell from './NotificationBell'

const CANDIDATE_LINKS = [
  { to: '/candidate', label: 'Обзор', end: true },
  { to: '/candidate/profile', label: 'Профиль', end: false },
  { to: '/candidate/assessment', label: 'Тест на грейд', end: false },
  { to: '/candidate/tasks', label: 'Задания', end: false },
  { to: '/candidate/offers', label: 'Приглашения', end: false },
  { to: '/candidate/vacancies', label: 'Вакансии', end: false },
  { to: '/candidate/results', label: 'Результаты ФСП', end: false },
]

const EMPLOYER_LINKS = [
  { to: '/employer', label: 'Обзор', end: true },
  { to: '/employer/needs', label: 'Потребности', end: false },
  { to: '/employer/search', label: 'Поиск', end: false },
  { to: '/employer/tasks', label: 'Задания', end: false },
  { to: '/employer/offers', label: 'Приглашения', end: false },
  { to: '/employer/vacancies', label: 'Вакансии', end: false },
  { to: '/employer/company', label: 'Компания', end: false },
]

export interface NavItem { to: string; label: string; end?: boolean }

export function ThemeToggle({ withLabel = false }: { withLabel?: boolean }) {
  const [theme, toggle] = useTheme()
  const label = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'
  const Icon = theme === 'dark' ? Sun : Moon
  if (withLabel) {
    return (
      <button type="button" onClick={toggle} className="btn-ghost w-full justify-start px-3 text-base font-medium">
        <Icon size={18} aria-hidden /> {label}
      </button>
    )
  }
  return (
    <button type="button" onClick={toggle} className="btn-icon" aria-label={label} title={label}>
      <Icon size={17} aria-hidden />
    </button>
  )
}

/** Phone navigation: one button opens a sheet with every section, the theme and sign-out. */
export function MobileMenu({ links, footer, label = 'Разделы' }: { links: NavItem[]; footer?: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="btn-icon md:hidden" aria-label="Открыть меню"
        aria-haspopup="dialog" aria-expanded={open}>
        <Menu size={20} aria-hidden />
      </button>
      {open && (
        <Modal titleId="mobile-menu-title" onClose={() => setOpen(false)} sheet>
          <div className="rounded-t-2xl border border-line bg-panel px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 shadow-pop sm:rounded-2xl">
            <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-line-strong sm:hidden" aria-hidden />
            <div className="flex items-center justify-between px-1 pb-2">
              <h2 id="mobile-menu-title" className="font-display text-sm font-bold text-ink">{label}</h2>
              <button type="button" onClick={() => setOpen(false)} className="btn-icon" aria-label="Закрыть меню"><X size={18} aria-hidden /></button>
            </div>
            <nav aria-label={label}>
              <ul className="grid gap-0.5">
                {links.map(({ to, label: text, end }) => {
                  const active = end ? pathname === to : pathname === to || pathname.startsWith(to + '/')
                  return (
                    <li key={to}>
                      <Link to={to} onClick={() => setOpen(false)} aria-current={active ? 'page' : undefined}
                        className={`flex min-h-11 items-center rounded-lg px-3 text-base transition-colors ${active
                          ? 'bg-accent-soft font-semibold text-accent' : 'text-ink hover:bg-sunken'}`}>
                        {text}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </nav>
            <div className="mt-2 grid gap-0.5 border-t border-line pt-2">
              <ThemeToggle withLabel />
              {footer}
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto grid max-w-page gap-4 px-4 py-8 text-xs text-ink-3 sm:px-6 md:grid-cols-[1fr_auto] md:items-start">
        <div className="max-w-[60ch] space-y-1.5">
          <p>ФСП Талант — прототип для Федерации спортивного программирования, ЛЦТ 2026. Демо-данные вымышлены.</p>
          <p>Контакты кандидата открываются только после его согласия.</p>
        </div>
        <nav aria-label="Справка">
          <ul className="flex flex-wrap gap-x-5 gap-y-2">
            <li><Link to="/legal" className="inline-flex min-h-6 items-center underline hover:text-ink">Документы и согласия</Link></li>
            <li><Link to="/method" className="inline-flex min-h-6 items-center underline hover:text-ink">Как устроен тест</Link></li>
            <li><Link to="/badge" className="inline-flex min-h-6 items-center underline hover:text-ink">Проверка удостоверения</Link></li>
            <li><Link to="/jury" className="inline-flex min-h-6 items-center underline hover:text-ink">Режим жюри</Link></li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}

export default function Layout() {
  const { userRole } = useAuthStore()
  const navigate = useNavigate()
  const links = userRole === 'participant' ? CANDIDATE_LINKS : EMPLOYER_LINKS
  const roleLabel = userRole === 'participant' ? 'Кандидат' : 'Работодатель'
  const exit = () => { void signOut().then(() => navigate('/')) }

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-panel/90 backdrop-blur-md supports-[backdrop-filter]:bg-panel/80">
        <div className="brand-stripe" aria-hidden />
        <div className="mx-auto flex h-14 max-w-page items-center justify-between gap-3 px-4 sm:h-16 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Brand to={userRole === 'participant' ? '/candidate' : '/employer'} />
            <span className="hidden rounded-full border border-line-strong px-2.5 py-0.5 text-2xs font-medium text-ink-2 sm:inline-flex">{roleLabel}</span>
          </div>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <span className="hidden md:inline-flex"><ThemeToggle /></span>
            <button type="button" onClick={exit} className="btn-nav gap-1.5 max-md:w-9 max-md:px-0" title="Выйти">
              <LogOut size={16} aria-hidden /><span className="sr-only md:not-sr-only">Выйти</span>
            </button>
            <MobileMenu links={links} label={`${roleLabel}: разделы`} />
          </div>
        </div>
        <nav aria-label="Разделы" className="mx-auto hidden max-w-page px-2 sm:px-4 md:block">
          <ul className="flex gap-1 overflow-x-auto scrollbar-none">
            {links.map(({ to, label, end }) => (
              <li key={to} className="shrink-0">
                <NavLink to={to} end={end} className={({ isActive }) =>
                  `relative flex min-h-10 items-center rounded-t-md px-3 pb-2.5 pt-1 text-sm transition-colors ${isActive
                    ? 'font-semibold text-ink after:absolute after:inset-x-3 after:-bottom-px after:h-[2px] after:rounded-full after:bg-accent'
                    : 'text-ink-2 hover:text-ink'}`}>
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-page flex-1 px-4 py-7 outline-none sm:px-6 sm:py-10">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}
