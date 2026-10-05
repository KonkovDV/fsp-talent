import { Link } from 'react-router-dom'

/** Product mark: a stylised «Т» (талант) in Federation navy with the red dot of the invitation. */
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="7" className="fill-navy dark:fill-accent" />
      <path d="M8.5 10h15M16 10v13" stroke="white" strokeWidth="3.4" fill="none" strokeLinecap="round" />
      <circle cx="23" cy="22" r="3" fill="#D42330" />
    </svg>
  )
}

export function Brand({ to = '/', compact = false }: { to?: string; compact?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 rounded-md" aria-label="ФСП Талант — на главную">
      <BrandMark />
      {!compact && (
        <span className="leading-none">
          <span className="block font-display text-[15px] font-semibold tracking-tight text-ink">ФСП Талант</span>
          <span className="block pt-1 text-2xs text-ink-3">подбор по результату</span>
        </span>
      )}
    </Link>
  )
}
