/** Anti-fake-vacancy fact: does the company open applications. Under five cases the number stays hidden. */
export interface ResponsivenessFact {
  shown: boolean; n: number; count?: number; lower?: number | null; note?: string
  median_days?: number | null; window_days?: number; within_days?: number
}

const pct = (v: number) => `${Math.round(v * 100)} %`
const days = (v: number) => v.toFixed(1).replace('.', ',').replace(/,0$/, '')

export default function Responsiveness({ fact, className = 'text-xs text-ink-3' }: { fact?: ResponsivenessFact | null; className?: string }) {
  if (!fact) return null
  const within = fact.within_days ?? 7
  const window = fact.window_days ?? 90
  if (!fact.shown) {
    return <p className={className} data-testid="responsiveness">Ответы на отклики: мало данных (меньше 5 откликов за {window} дней)</p>
  }
  return (
    <p className={className} data-testid="responsiveness">
      Открывает отклики за {within} дней: не реже {pct(fact.lower ?? 0)} (по {fact.n} откликам за {window} дней)
      {fact.median_days != null ? `, в среднем (медиана) через ${days(fact.median_days)} дн.` : ''}
    </p>
  )
}
