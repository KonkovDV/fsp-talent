/** Labels match backend services/market.py DECLINE_LABELS. */
export const DECLINE_LABELS: Record<string, string> = {
  salary: 'Зарплата', format: 'Формат работы', stack: 'Стек', not_looking: 'Сейчас не ищу', other: 'Другое',
}

/** Why this employer's own invitations were declined, most frequent first. A refusal without a reason is «Не указана». */
export function declineReasons(offers: { status: string; decline_reason?: string | null }[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const o of offers) {
    if (o.status !== 'rejected') continue
    const label = (o.decline_reason && DECLINE_LABELS[o.decline_reason]) || 'Не указана'
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ru'))
}
