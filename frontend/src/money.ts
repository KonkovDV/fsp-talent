/** Progressive NDFL, Tax Code art. 224 since 2025. Same bands as backend/app/services/salary_net.py. */
const BANDS: [number | null, number][] = [
  [2_400_000, 13], [5_000_000, 15], [20_000_000, 18], [50_000_000, 20], [null, 22],
]

export function annualTax(income: number): number {
  let tax = 0
  let prev = 0
  for (const [edge, rate] of BANDS) {
    if (income <= prev) break
    const top = edge == null ? income : Math.min(income, edge)
    tax += Math.floor((top - prev) * rate / 100)
    if (edge == null || income <= edge) break
    prev = edge
  }
  return tax
}

/** Take-home for one month, rounded to 100 rubles. */
export function netMonthly(gross: number): number {
  if (!gross || gross < 0) return 0
  const net = gross * 12 - annualTax(gross * 12)
  return Math.round(net / 12 / 100) * 100
}

export function grossForNet(net: number): number {
  if (!net || net < 0) return 0
  let lo = net
  let hi = Math.max(net, 1)
  while (netMonthly(hi) < net && hi < 100_000_000) hi = Math.min(hi * 2, 100_000_000)
  let best = hi
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2)
    if (netMonthly(mid) < net) lo = mid + 1
    else { best = mid; hi = mid - 1 }
  }
  return best
}

const fmt = (n: number) => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(n)

/** «на руки ≈ …» under a gross range. Empty when both ends are missing. */
export function netLine(from?: number | null, to?: number | null): string {
  const a = from ? netMonthly(from) : 0
  const b = to ? netMonthly(to) : 0
  if (!a && !b) return ''
  if (a && b && a !== b) return `на руки ≈ ${fmt(a)}–${fmt(b)} ₽`
  return `на руки ≈ ${fmt(a || b)} ₽`
}
