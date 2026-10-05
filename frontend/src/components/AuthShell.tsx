import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Brand } from './Brand'
import { ThemeToggle } from './Layout'

/** Frame for sign-in, sign-up and email confirmation: one narrow column, brand on top, nothing else to read. */
export default function AuthShell({ title, lead, children, aside }: {
  title: string; lead?: ReactNode; children: ReactNode; aside?: ReactNode
}) {
  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <div className="brand-stripe" aria-hidden />
      <header className="mx-auto flex w-full max-w-page items-center justify-between px-4 py-5 sm:px-6">
        <Brand />
        <ThemeToggle />
      </header>
      <main id="main" className="flex flex-1 items-start justify-center px-4 pb-16 pt-4 sm:pt-10">
        <div className="w-full max-w-md animate-rise">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h1>
          {lead && <div className="mt-2 text-sm text-ink-2">{lead}</div>}
          <div className="mt-7 rounded-xl border border-line bg-panel p-6 sm:p-7">{children}</div>
          {aside && <div className="mt-5 text-center text-sm text-ink-2">{aside}</div>}
        </div>
      </main>
      <footer className="px-4 pb-6 text-center text-xs text-ink-3">
        <Link to="/" className="hover:text-ink">На главную</Link>
      </footer>
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
