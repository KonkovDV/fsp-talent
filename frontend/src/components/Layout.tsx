import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { LogOut, Sun, Moon } from 'lucide-react'
import { useState, useEffect } from 'react'

export default function Layout() {
  const { userRole, logout } = useAuthStore()
  const navigate = useNavigate()
  const [dark, setDark] = useState(true)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  }, [dark])

  const handleLogout = () => { logout(); navigate('/') }

  const candidateLinks = [
    { to: '/candidate',           label: 'Обзор',      end: true },
    { to: '/candidate/profile',   label: 'Профиль' },
    { to: '/candidate/results',   label: 'Результаты' },
    { to: '/candidate/offers',    label: 'Офферы' },
    { to: '/candidate/vacancies', label: 'Вакансии' },
  ]

  const employerLinks = [
    { to: '/employer',            label: 'Дашборд', end: true },
    { to: '/employer/search',     label: 'Поиск' },
    { to: '/employer/offers',     label: 'Офферы' },
    { to: '/employer/vacancies',  label: 'Вакансии' },
  ]

  const links = userRole === 'participant' ? candidateLinks : employerLinks

  return (
    <div className="min-h-dvh flex flex-col bg-surface-0">
      {/* Glass header */}
      <header className="glass-nav sticky top-0 z-40" role="banner">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-8">
            <a href="/" className="flex items-center gap-2 select-none" aria-label="FSP Talent — главная">
              <div className="w-7 h-7 rounded-lg bg-brand flex items-center justify-center text-white text-xs font-bold glow-brand">
                F
              </div>
              <span className="text-sm font-bold text-text-primary">FSP Talent</span>
            </a>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-0.5" aria-label="Главная навигация">
              {links.map(l => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  end={l.end}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                      isActive
                        ? 'bg-brand/20 text-brand-bright'
                        : 'text-text-secondary hover:text-text-primary hover:bg-surface-2'
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDark(d => !d)}
              className="btn-ghost w-8 h-8 p-0 rounded-lg"
              aria-label={dark ? 'Светлая тема' : 'Тёмная тема'}
            >
              {dark ? <Sun size={15}/> : <Moon size={15}/>}
            </button>
            <button
              onClick={handleLogout}
              className="btn-ghost text-xs gap-1.5"
              aria-label="Выйти"
            >
              <LogOut size={14}/> Выйти
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main id="main" className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
