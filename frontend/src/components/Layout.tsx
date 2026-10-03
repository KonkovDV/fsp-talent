import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { LogOut } from 'lucide-react'

export default function Layout() {
  const { userRole, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/') }

  const candidateLinks = [
    { to: '/candidate', label: 'Дашборд', end: true },
    { to: '/candidate/profile', label: 'Профиль' },
    { to: '/candidate/results', label: 'Результаты' },
    { to: '/candidate/offers', label: 'Офферы' },
  ]

  const employerLinks = [
    { to: '/employer', label: 'Дашборд', end: true },
    { to: '/employer/search', label: 'Поиск' },
    { to: '/employer/offers', label: 'Офферы' },
  ]

  const links = userRole === 'participant' ? candidateLinks : employerLinks

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <span className="text-xl font-bold text-fsp-violet">FSP Talent</span>
            <nav className="hidden md:flex items-center gap-1">
              {links.map(l => (
                <NavLink key={l.to} to={l.to} end={l.end}
                  className={({ isActive }) =>
                    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-fsp-violet/10 text-fsp-violet' : 'text-gray-600 hover:bg-gray-100'
                    }`
                  }>
                  {l.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleLogout}
              className="flex items-center gap-2 text-sm text-gray-500 hover:text-fsp-red transition-colors">
              <LogOut size={16} /> Выйти
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
