/** Compare employer match rankings across views (localStorage, per need). */

export type RankedId = { id: string; place: number }

export type CardMarker = 'new' | 'up' | 'down'

export type SelectionDiff = {
  added: number
  removed: number
  moved: number
  markers: Record<string, CardMarker>
}

const PREFIX = 'fsp.selection:'

export function selectionStorageKey(needId: string): string {
  return `${PREFIX}${needId}`
}

export function loadSnapshot(needId: string): RankedId[] | null {
  if (typeof localStorage === 'undefined') return null
  try {
    const raw = localStorage.getItem(selectionStorageKey(needId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return null
    const out: RankedId[] = []
    for (const row of parsed) {
      if (!row || typeof row !== 'object') continue
      const id = (row as { id?: unknown }).id
      const place = (row as { place?: unknown }).place
      if (typeof id === 'string' && typeof place === 'number' && Number.isFinite(place)) {
        out.push({ id, place })
      }
    }
    return out.length ? out : null
  } catch {
    return null
  }
}

export function saveSnapshot(needId: string, ranks: RankedId[]): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(selectionStorageKey(needId), JSON.stringify(ranks))
  } catch {
    /* private mode / quota */
  }
}

export function ranksFromIds(ids: string[]): RankedId[] {
  return ids.map((id, i) => ({ id, place: i + 1 }))
}

export function diffSelection(prev: RankedId[] | null, next: RankedId[]): SelectionDiff {
  if (!prev || prev.length === 0) {
    return { added: 0, removed: 0, moved: 0, markers: {} }
  }
  const prevPlace = new Map(prev.map(r => [r.id, r.place]))
  const nextIds = new Set(next.map(r => r.id))
  let added = 0
  let moved = 0
  const markers: Record<string, CardMarker> = {}
  for (const row of next) {
    const before = prevPlace.get(row.id)
    if (before === undefined) {
      added += 1
      markers[row.id] = 'new'
    } else if (before !== row.place) {
      moved += 1
      markers[row.id] = before > row.place ? 'up' : 'down'
    }
  }
  let removed = 0
  for (const row of prev) {
    if (!nextIds.has(row.id)) removed += 1
  }
  return { added, removed, moved, markers }
}

/** «+3 новых · −2 выбыли · 5 сдвинулись», or null when nothing to show. */
export function formatSelectionSummary(diff: SelectionDiff): string | null {
  const parts: string[] = []
  if (diff.added) parts.push(`+${diff.added} ${ruCount(diff.added, 'новый', 'новых', 'новых')}`)
  if (diff.removed) parts.push(`−${diff.removed} ${ruCount(diff.removed, 'выбыл', 'выбыли', 'выбыли')}`)
  if (diff.moved) parts.push(`${diff.moved} ${ruCount(diff.moved, 'сдвинулся', 'сдвинулись', 'сдвинулись')}`)
  return parts.length ? parts.join(' · ') : null
}

function ruCount(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
