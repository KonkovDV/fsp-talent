import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { LogOut, Sun, Moon, LayoutDashboard, User, Trophy, Gift, Briefcase, Search, FileText, ClipboardCheck } from 'lucide-react'
import { useState, useEffect } from 'react'

/** ФСП diamond logo mark */
function FspLogo({ size = 28 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5 select-none" aria-hidden>
      <div
        style={{
          width: size, height: size,
          background: 'linear-gradient(135deg, #D42330, #FF4D5A)',
          clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <span style={{ color: '#fff', fontWeight: 900, fontSize: size * 0.35, letterSpacing: '-0.03em' }}>Ф</span>
      </div>
      <div className="flex flex-col" style={{ lineHeight: 1 }}>
        <span style={{ color: '#fff', fontWeight: 900, fontSize: 13, letterSpacing: '0.04em' }}>ФСП</span>
        <span style={{ color: 'rgba(255,255,255,0.6)', fontWeight: 500, fontSize: 9, letterSpacing: '0.08em' }}>ТАЛАНТ</span>
      </div>
    </div>
  )
}

const CANDIDATE_LINKS = [
  { to: '/candidate',           label: 'Обзор',      end: true,  Icon: LayoutDashboard },
  { to: '/candidate/profile',   label: 'Профиль',    end: false, Icon: User },
  { to: '/candidate/assessment', label: 'Тест на грейд', end: false, Icon: ClipboardCheck },
  { to: '/candidate/results',   label: 'Результаты', end: false, Icon: Trophy },
  { to: '/candidate/offers',    label: 'Офферы',     end: false, Icon: Gift },
  { to: '/candidate/vacancies', label: 'Вакансии',   end: false, Icon: Briefcase },
]

const EMPLOYER_LINKS = [
  { to: '/employer',           label: 'Дашборд',  end: true,  Icon: LayoutDashboard },
  { to: '/employer/needs',     label: 'Потребности', end: false, Icon: ClipboardCheck },
  { to: '/employer/search',    label: 'Поиск',    end: false, Icon: Search },
  { to: '/employer/offers',    label: 'Офферы',   end: false, Icon: Gift },
  { to: '/employer/vacancies', label: 'Вакансии', end: false, Icon: FileText },
]

export default function Layout() {
  const { userRole, logout } = useAuthStore()
  const navigate = useNavigate()
  const [dark, setDark] = useState(true)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  }, [dark])

  const handleLogout = () => { logout(); navigate('/') }
  const links = userRole === 'participant' ? CANDIDATE_LINKS : EMPLOYER_LINKS

  return (
    <div className="min-h-dvh flex flex-col bg-surface-0">

      {/* ── ФСП Navy Header ─────────────────────────────────── */}
      <header className="fsp-nav sticky top-0 z-40" role="banner">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">

          {/* Logo + Nav */}
          <div className="flex items-center gap-6">
            <a href="/" aria-label="ФСП Талант — главная">
              <FspLogo size={28} />
            </a>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-0.5" aria-label="Разделы">
              {links.map(({ to, label, end, Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-semibold transition-all duration-150 ${
                      isActive
                        ? 'bg-white/20 text-white'
                        : 'text-white/65 hover:text-white hover:bg-white/10'
                    }`
                  }
                >
                  <Icon size={13} aria-hidden />
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setDark(d => !d)}
              className="btn-nav w-8 h-8 p-0"
              aria-label={dark ? 'Светлая тема' : 'Тёмная тема'}
            >
              {dark ? <Sun size={14} /> : <Moon size={14} />}
            </button>
            <button
              onClick={handleLogout}
              className="btn-nav text-xs gap-1.5"
              aria-label="Выйти"
            >
              <LogOut size={13} /> Выйти
            </button>
          </div>
        </div>

        {/* ── Red accent underline ── */}
        <div style={{ height: 2, background: 'linear-gradient(90deg, #D42330, #FF4D5A, #D42330)' }} aria-hidden />
      </header>

      {/* Content */}
      <main id="main" className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8" tabIndex={-1}>
        <Outlet />
      </main>

      {/* ── Footer strip ── */}
      <footer style={{ background: '#0A1F5C', borderTop: '1px solid rgba(255,255,255,0.1)' }} className="py-3">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <FspLogo size={22} />
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11 }}>
            &copy; 2026 Федерация спортивного программирования · контакты только после согласия
          </p>
        </div>
      </footer>
    </div>
  )
}
