import { X } from 'lucide-react'
import { Meter } from './ui'

export interface PassportSkill {
  name: string
  trust_level?: string | null
  source_quote?: string | null
  created_at?: string | null
  confirmed_at?: string | null
}

const TRUST: Record<string, { label: string; weight: number }> = {
  test_confirmed: { label: 'Подтверждён тестом', weight: 1 },
  resume_confirmed: { label: 'Цитата из резюме', weight: 0.75 },
  self_reported: { label: 'Заявлен', weight: 0.55 },
}

const ORDER = ['test_confirmed', 'resume_confirmed', 'self_reported']

function ruDate(iso?: string | null): string | null {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString('ru-RU')
}

/** One row of the skill passport: where the skill came from, when, and how much the match trusts it. */
export default function SkillPassport({ skills, onRemove }: {
  skills: PassportSkill[]
  onRemove?: (name: string) => void
}) {
  const rows = [...skills].sort((a, b) => {
    const rank = ORDER.indexOf(a.trust_level ?? 'self_reported') - ORDER.indexOf(b.trust_level ?? 'self_reported')
    return rank || a.name.localeCompare(b.name, 'ru')
  })
  if (rows.length === 0) return <p className="text-sm text-ink-3">Навыков пока нет: добавьте вручную или разберите резюме.</p>
  return (
    <ul className="divide-y divide-line">
      {rows.map(skill => {
        const trust = TRUST[skill.trust_level ?? ''] ?? TRUST.self_reported
        const date = ruDate(skill.trust_level === 'self_reported' ? skill.created_at : skill.confirmed_at ?? skill.created_at)
        return (
          <li key={skill.name} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 py-3">
            <p className={`min-w-0 truncate text-sm font-medium text-ink ${onRemove ? '' : 'col-span-2'}`}>{skill.name}</p>
            {onRemove && (
              <button type="button" onClick={() => onRemove(skill.name)} aria-label={`Убрать ${skill.name}`}
                className="rounded-full p-1 text-ink-3 hover:bg-sunken hover:text-ink"><X size={14} /></button>
            )}
            <p className="col-span-2 text-xs text-ink-2">
              {date ? (skill.trust_level === 'resume_confirmed' ? `${trust.label} от ${date}` : `${trust.label} ${date}`) : trust.label}
            </p>
            {skill.source_quote && onRemove && (
              <p className="col-span-2 truncate text-xs text-ink-3" title={skill.source_quote}>{skill.source_quote}</p>
            )}
            <div className="col-span-2 max-w-xs">
              <Meter value={trust.weight} ariaLabel={`${skill.name}: ${trust.label}, вес ${Math.round(trust.weight * 100)} из 100`} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
