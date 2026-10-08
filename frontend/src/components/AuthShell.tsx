import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Brand, BrandMark } from './Brand'
import { ThemeToggle } from './chrome'
import RussiaNetwork from './RussiaNetwork'

/** Frame for sign-in, sign-up and email confirmation: one narrow column, brand on top, nothing else to read. */
export default function AuthShell({ title, lead, children, aside }: {
  title: string; lead?: ReactNode; children: ReactNode; aside?: ReactNode
}) {
  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col justify-between overflow-hidden bg-[#402FFF] p-10 text-white lg:flex xl:p-14" aria-hidden>
        <Link to="/" className="flex items-center gap-2.5" tabIndex={-1}>
          <BrandMark size={30} tile />
          <span className="font-display text-[15px] font-extrabold tracking-[-0.02em]">ФСП Талант</span>
        </Link>
        <div>
          <p className="max-w-[16ch] font-display text-[2.5rem] font-bold leading-[1.08] tracking-[-0.03em]">Категория, которой можно верить</p>
          <ul className="mt-8 grid max-w-md gap-3 text-[0.9375rem] text-white/90">
            {['Грейд подтверждает адаптивный тест', 'Достижения — из протоколов ФСП', 'Контакты — только после согласия'].map(t => (
              <li key={t} className="flex items-center gap-3 border-t border-white/20 pt-3"><span className="h-1.5 w-1.5 shrink-0 rounded-full bg-white" />{t}</li>
            ))}
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
            <h1 className="font-display text-[1.75rem] font-bold leading-tight tracking-[-0.03em] text-ink">{title}</h1>
            {lead && <div className="mt-2 text-sm text-ink-2">{lead}</div>}
            <div className="mt-7 rounded-2xl border border-line-strong/70 bg-panel p-6 shadow-xs dark:border-line sm:p-8">{children}</div>
            {aside && <div className="mt-5 text-center text-sm text-ink-2">{aside}</div>}
          </div>
        </main>
        <footer className="px-4 pb-6 text-center text-xs text-ink-3">
          <Link to="/" className="inline-flex min-h-6 items-center underline hover:text-ink">На главную</Link>
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
          className={`flex min-h-9 items-center justify-center rounded-md text-center transition-colors ${r === role ? 'bg-panel font-semibold text-ink shadow-xs ring-1 ring-line-strong' : 'text-ink-2 hover:text-ink'}`}>
          {r === 'participant' ? 'Кандидат' : 'Работодатель'}
        </Link>
      ))}
    </div>
  )
}
