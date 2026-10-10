import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { signOut } from '../api/client'
import { useAuthStore } from '../store/authStore'
import { Brand } from './Brand'
import GuideBox from './GuideBox'
import NotificationBell from './NotificationBell'
import { MobileMenu, SiteFooter, ThemeToggle } from './chrome'

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
  { to: '/employer/favorites', label: 'Избранное', end: false },
  { to: '/employer/tasks', label: 'Задания', end: false },
  { to: '/employer/offers', label: 'Приглашения', end: false },
  { to: '/employer/vacancies', label: 'Вакансии', end: false },
  { to: '/employer/company', label: 'Компания', end: false },
  { to: '/employer/integrations', label: 'Интеграции', end: false },
  { to: '/employer/moderation', label: 'Модерация', end: false },
  { to: '/employer/methodist', label: 'Методист', end: false },
]

export default function Layout() {
  const { userRole, guestUntil } = useAuthStore()
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
            {userRole && <GuideBox role={userRole === 'participant' ? 'participant' : 'employer'} />}
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
        {guestUntil && (
          <p className="notice-info mb-6 text-sm" data-testid="guest-banner">
            Гостевой аккаунт: данные удалятся {new Date(guestUntil).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}.
            Чтобы сохранить работу, зарегистрируйтесь с почтой.
          </p>
        )}
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}
