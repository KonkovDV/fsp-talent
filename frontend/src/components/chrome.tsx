import { useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, Moon, Sun, X } from 'lucide-react'
import { useTheme } from '../lib/theme'
import Modal from './Modal'

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
      <div className="mx-auto grid max-w-page gap-4 px-4 py-8 text-xs text-ink-3 sm:px-6 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:items-start" data-testid="site-footer-grid">
        <div className="min-w-0 max-w-[60ch] space-y-1.5 [overflow-wrap:anywhere]">
          <p>ФСП Талант · команда Дмитрия Конькова. Самостоятельный проект, лицензия MIT. Демо-данные вымышлены.</p>
          <p>Контакты кандидата открываются только после его согласия.</p>
          <p>Наименование ФСП указывает предметную область. Сервис не является официальным ресурсом Федерации спортивного программирования.</p>
          <p>Подпись W3C Verifiable Credentials подтверждает, что данные не изменены после выдачи. Это не электронная подпись в смысле Федерального закона № 63-ФЗ.</p>
        </div>
        <nav aria-label="Справка" className="min-w-0">
          <ul className="flex flex-wrap gap-x-5 gap-y-2 md:justify-end">
            <li><Link to="/legal" className="inline-flex min-h-6 items-center underline hover:text-ink">Документы и согласия</Link></li>
            <li><Link to="/privacy" className="inline-flex min-h-6 items-center underline hover:text-ink">Политика обработки данных</Link></li>
            <li><Link to="/method" className="inline-flex min-h-6 items-center underline hover:text-ink">Как устроен тест</Link></li>
            <li><Link to="/badge" className="inline-flex min-h-6 items-center underline hover:text-ink">Проверка удостоверения</Link></li>
            <li><Link to="/evaluate" className="inline-flex min-h-6 items-center underline hover:text-ink">Подбор на своей разметке</Link></li>
            <li><Link to="/jury" className="inline-flex min-h-6 items-center underline hover:text-ink">Режим жюри</Link></li>
            <li><a href="/docs" target="_blank" rel="noopener" className="inline-flex min-h-6 items-center underline hover:text-ink">API (Swagger)</a></li>
          </ul>
        </nav>
      </div>
    </footer>
  )
}
