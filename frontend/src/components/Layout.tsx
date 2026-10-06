import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut, Moon, Sun } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useTheme } from '../lib/theme'
import { Brand } from './Brand'
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

export function ThemeToggle() {
  const [theme, toggle] = useTheme()
  return (
    <button onClick={toggle} className="btn-nav h-9 w-9 p-0" aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
      title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
      {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  )
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-page flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-ink-3 sm:px-6">
        <p>ФСП Талант — прототип для Федерации спортивного программирования, ЛЦТ 2026. Демо-данные вымышлены.</p>
        <p>Контакты кандидата открываются только после его согласия. <Link to="/legal" className="underline hover:text-ink">Документы и согласия</Link></p>
      </div>
    </footer>
  )
}

export default function Layout() {
  const { userRole, logout } = useAuthStore()
  const navigate = useNavigate()
  const links = userRole === 'participant' ? CANDIDATE_LINKS : EMPLOYER_LINKS
  const roleLabel = userRole === 'participant' ? 'Кандидат' : 'Работодатель'

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <header className="sticky top-0 z-40 border-b border-line bg-panel/95 backdrop-blur supports-[backdrop-filter]:bg-panel/85">
        <div className="brand-stripe" aria-hidden />
        <div className="mx-auto flex h-16 max-w-page items-center justify-between gap-4 px-4 sm:px-6">
          <Brand to={userRole === 'participant' ? '/candidate' : '/employer'} />
          <div className="flex items-center gap-1">
            <span className="mr-2 hidden text-xs text-ink-3 sm:inline">{roleLabel}</span>
            <NotificationBell />
            <ThemeToggle />
            <button onClick={() => { logout(); navigate('/') }} className="btn-nav gap-1.5 text-xs">
              <LogOut size={15} aria-hidden /> Выйти
            </button>
          </div>
        </div>
        <nav aria-label="Разделы" className="mx-auto max-w-page overflow-x-auto px-2 [mask-image:linear-gradient(90deg,#000_82%,transparent)] sm:px-4 md:[mask-image:none]">
          <ul className="flex min-w-max gap-1">
            {links.map(({ to, label, end }) => (
              <li key={to}>
                <NavLink to={to} end={end} className={({ isActive }) =>
                  `relative block px-3 pb-3 pt-1 text-sm transition-colors ${isActive
                    ? 'font-semibold text-ink after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-accent'
                    : 'text-ink-2 hover:text-ink'}`}>
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="mx-auto w-full max-w-page flex-1 px-4 py-8 outline-none sm:px-6 sm:py-10">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}
