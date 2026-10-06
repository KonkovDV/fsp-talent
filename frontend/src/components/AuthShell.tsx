import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './Brand'
import { ThemeToggle } from './Layout'
import RussiaNetwork from './RussiaNetwork'

/** Frame for sign-in, sign-up and email confirmation: one narrow column, brand on top, nothing else to read. */
export default function AuthShell({ title, lead, children, aside }: {
  title: string; lead?: ReactNode; children: ReactNode; aside?: ReactNode
}) {
  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-[#402FFF] p-10 text-white lg:flex" aria-hidden>
        <Link to="/" className="flex items-center gap-2.5" tabIndex={-1}>
          <svg width={28} height={28} viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#fff" /><path d="M8.5 10h15M16 10v13" stroke="#402FFF" strokeWidth="3.4" fill="none" strokeLinecap="round" /><circle cx="23" cy="22" r="3" fill="#EC1D35" /></svg>
          <span className="font-display text-[15px] font-bold">ФСП Талант</span>
        </Link>
        <div>
          <p className="max-w-[18ch] font-display text-3xl font-bold leading-tight tracking-tight">Категория, которой можно верить</p>
          <ul className="mt-6 space-y-2 text-sm text-white/85">
            <li>Грейд подтверждает адаптивный тест</li>
            <li>Достижения — из протоколов ФСП</li>
            <li>Контакты — только после согласия</li>
          </ul>
        </div>
        <RussiaNetwork onBrand className="w-full max-w-lg" />
      </aside>
      <div className="flex min-h-dvh flex-col">
        <div className="brand-stripe" aria-hidden />
        <header className="flex w-full items-center justify-between px-4 py-5 sm:px-8">
          <span className="lg:invisible"><Brand /></span>
          <ThemeToggle />
        </header>
        <main id="main" className="flex flex-1 items-start justify-center px-4 pb-16 pt-4 sm:pt-10 lg:items-center lg:pt-0">
          <div className="w-full max-w-md animate-rise">
            <h1 className="font-display text-2xl font-bold tracking-tight text-ink">{title}</h1>
            {lead && <div className="mt-2 text-sm text-ink-2">{lead}</div>}
            <div className="mt-7 rounded-xl border border-line bg-panel p-6 sm:p-7">{children}</div>
            {aside && <div className="mt-5 text-center text-sm text-ink-2">{aside}</div>}
          </div>
        </main>
        <footer className="px-4 pb-6 text-center text-xs text-ink-3">
          <Link to="/" className="hover:text-ink">На главную</Link>
        </footer>
      </div>
    </div>
  )
}

/** Two-option switch for the role on auth screens. */
export function RoleSwitch({ role, base }: { role: 'participant' | 'employer'; base: string }) {
  return (
    <div className="mb-6 grid grid-cols-2 rounded-lg bg-sunken p-1 text-sm" role="tablist" aria-label="Роль">
      {(['participant', 'employer'] as const).map(r => (
        <Link key={r} to={`${base}?role=${r}`} role="tab" aria-selected={r === role}
          className={`rounded-md py-2 text-center transition-colors ${r === role ? 'bg-panel font-semibold text-ink shadow-sm ring-1 ring-line-strong' : 'text-ink-2 hover:text-ink'}`}>
          {r === 'participant' ? 'Кандидат' : 'Работодатель'}
        </Link>
      ))}
    </div>
  )
}
