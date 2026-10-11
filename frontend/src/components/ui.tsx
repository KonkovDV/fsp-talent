import type { ReactNode } from 'react'
import { Check } from 'lucide-react'
import { ROLE_RU, gradeRu } from '../labels'

export function PageHeader({ title, lead, actions }: { title: string; lead?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="min-w-0 max-w-full">
        <h1 className="page-title" title={typeof title === 'string' ? title : undefined}>{title}</h1>
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
      {label && <p className={`mt-1.5 truncate text-[11px] leading-4 ${value === null ? 'text-ink-3 line-through' : 'text-ink-3'}`}>{label}</p>}
    </div>
  )
}

/** The category plate: specialization × grade, like a start number. Source tells how the grade is known. */
export function CategoryPlate({ role, grade, source, size = 'md' }: {
  role: string | null | undefined; grade: string | null | undefined; source?: string | null; size?: 'md' | 'lg'
}) {
  const confirmed = source === 'assessed'
  const pad = size === 'lg' ? 'px-3 py-1.5' : 'px-2.5 py-1'
  return (
    <span className={`inline-flex items-stretch overflow-hidden rounded-md bg-panel ring-1 ring-inset ${confirmed ? 'ring-accent' : 'ring-line-strong'} ${size === 'lg' ? 'text-base' : 'text-xs'}`}
      title={confirmed ? 'Грейд подтверждён тестом' : undefined}>
      <span className={`${pad} font-medium text-ink`}>{ROLE_RU[role ?? ''] ?? role ?? 'роль не задана'}</span>
      <span className={`flex items-center gap-1 whitespace-nowrap ${pad} font-display font-bold ${confirmed ? 'bg-accent text-accent-ink' : 'border-l border-dashed border-line-strong bg-sunken text-ink-2'}`}>
        {grade ? gradeRu(grade) : '—'}
        {confirmed && <Check size={size === 'lg' ? 15 : 12} strokeWidth={3} aria-hidden />}
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

export function RankBadge({ rank, assignedAt, orderRef }: {
  rank: string | null | undefined
  assignedAt?: string | null
  orderRef?: string | null
}) {
  if (!rank) return null
  const cls = rank === 'МС' ? 'badge-mc' : rank === 'КМС' ? 'badge-kmc' : 'badge-vc'
  const title = assignedAt || orderRef
    ? `Разряд по данным реестра ФСП: присвоен ${assignedAt ? assignedAt.slice(0, 10) : 'дата не указана'}, ${orderRef || 'приказ не указан'}`
    : 'Разряд по данным реестра ФСП'
  return <span className={cls} title={title}>{rank}</span>
}

export function Empty({ title, children, action, icon }: { title: string; children?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-accent-soft text-accent" aria-hidden>{icon}</div>}
      <p className="font-display text-sm font-bold text-ink">{title}</p>
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
