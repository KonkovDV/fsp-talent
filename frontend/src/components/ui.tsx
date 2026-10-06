import type { ReactNode } from 'react'
import { ROLE_RU, gradeRu } from '../labels'

export function PageHeader({ title, lead, actions }: { title: string; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="min-w-0">
        <h1 className="page-title">{title}</h1>
        {lead && <p className="page-lead">{lead}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Meter({ value, label, muted, ariaLabel }: { value: number | null; label?: string; muted?: boolean; ariaLabel?: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, Math.round(value * 100)))
  return (
    <div>
      <div className="meter" role={value === null ? undefined : 'meter'} aria-valuenow={value === null ? undefined : pct}
        aria-valuemin={0} aria-valuemax={100} aria-label={label ?? ariaLabel}>
        {value !== null && <span style={{ width: `${pct}%` }} className={muted ? '!bg-ink-3' : ''} />}
      </div>
      {label && <p className={`mt-1 truncate text-[11px] ${value === null ? 'text-ink-3 line-through' : 'text-ink-3'}`}>{label}</p>}
    </div>
  )
}

/** The category plate: specialization × grade, like a start number. Source tells how the grade is known. */
export function CategoryPlate({ role, grade, source, size = 'md' }: {
  role: string | null | undefined; grade: string | null | undefined; source?: string | null; size?: 'md' | 'lg'
}) {
  const confirmed = source === 'assessed'
  return (
    <span className={`inline-flex items-stretch overflow-hidden rounded-md ring-1 ring-inset ${confirmed ? 'ring-accent' : 'ring-line-strong'} ${size === 'lg' ? 'text-base' : 'text-xs'}`}>
      <span className={`px-2.5 ${size === 'lg' ? 'py-1.5' : 'py-1'} font-medium text-ink`}>{ROLE_RU[role ?? ''] ?? role ?? 'роль не задана'}</span>
      <span className={`flex items-center whitespace-nowrap px-2.5 ${size === 'lg' ? 'py-1.5' : 'py-1'} font-display font-bold ${confirmed ? 'bg-accent text-accent-ink' : 'bg-sunken text-ink-2'}`}>
        {grade ? gradeRu(grade) : '—'}
      </span>
    </span>
  )
}

export const SOURCE_LABEL: Record<string, string> = {
  assessed: 'подтверждён тестом',
  declared: 'заявлен, не проверен',
  experience: 'оценка по стажу',
  default: 'не указан',
}

export function RankBadge({ rank }: { rank: string | null | undefined }) {
  if (!rank) return null
  const cls = rank === 'МС' || rank === 'МСМК' ? 'badge-mc' : rank === 'КМС' ? 'badge-kmc' : 'badge-vc'
  return <span className={cls} title="Разряд-эквивалент по результатам ФСП">{rank}</span>
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-prose">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function Skeleton({ className = 'h-24' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />
}

export const rub = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n) + ' ₽'

export const date = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString('ru-RU') : '—')

/** Russian plural: plural(3, ['потребность', 'потребности', 'потребностей']) → «потребности». */
export function plural(n: number, [one, few, many]: [string, string, string]): string {
  const a = Math.abs(n) % 100, b = a % 10
  if (a > 10 && a < 20) return many
  if (b === 1) return one
  if (b >= 2 && b <= 4) return few
  return many
}
