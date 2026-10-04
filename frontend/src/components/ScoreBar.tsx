interface ScoreBarProps {
  mu: number
  lcb: number
  sigma?: number
  label?: string
  compact?: boolean
}

/** μ score → human label */
function muLabel(v: number): string {
  if (v >= 0.80) return 'Высокий'
  if (v >= 0.60) return 'Выше среднего'
  if (v >= 0.40) return 'Средний'
  if (v >= 0.20) return 'Ниже среднего'
  return 'Начинающий'
}

export default function ScoreBar({ mu, lcb, sigma, label, compact }: ScoreBarProps) {
  const muPct  = Math.max(0, Math.min(100, Math.round(mu  * 100)))
  const lcbPct = Math.max(0, Math.min(100, Math.round(lcb * 100)))

  return (
    <div className={compact ? 'space-y-1.5' : 'space-y-2.5'}>
      {label && <p className="text-xs font-semibold text-text-secondary">{label}</p>}

      {/* ── μ (Bayesian score) — ФСП Gold ── */}
      <div className="flex items-center gap-3">
        <span className="text-2xs text-text-muted w-28 shrink-0">Байесовский скор (μ)</span>
        <div
          className="flex-1 relative h-2 rounded-full overflow-hidden"
          style={{ background: 'oklch(var(--score-track))' }}
        >
          <div
            style={{
              width: `${muPct}%`,
              height: '100%',
              borderRadius: 9999,
              background: 'linear-gradient(90deg, #C47F00, #F0A500, #FFD04A)',
              transition: 'width 0.7s ease-out',
            }}
            role="progressbar"
            aria-label={`Байесовский скор: ${mu.toFixed(2)} (${muLabel(mu)})`}
            aria-valuenow={muPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
        <span
          className="text-sm font-black tabular w-10 text-right"
          style={{ color: '#F0A500' }}
        >
          {mu.toFixed(2)}
        </span>
      </div>

      {/* ── LCB (Lower Confidence Bound) — ФСП Electric Blue ── */}
      <div className="flex items-center gap-3">
        <span className="text-2xs text-text-muted w-28 shrink-0">Нижняя граница (LCB)</span>
        <div
          className="flex-1 relative h-2 rounded-full overflow-hidden"
          style={{ background: 'oklch(var(--score-track))' }}
        >
          <div
            style={{
              width: `${lcbPct}%`,
              height: '100%',
              borderRadius: 9999,
              background: 'linear-gradient(90deg, #1B3FA0, #1D82F5, #5BADFF)',
              transition: 'width 0.7s ease-out',
            }}
            role="progressbar"
            aria-label={`Нижняя граница: ${lcb.toFixed(2)}`}
            aria-valuenow={lcbPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
        <span
          className="text-sm font-black tabular w-10 text-right"
          style={{ color: '#1D82F5' }}
        >
          {lcb.toFixed(2)}
        </span>
      </div>

      {sigma !== undefined && (
        <p className="text-2xs text-text-muted">σ = {sigma.toFixed(3)} · {muLabel(mu)}</p>
      )}
    </div>
  )
}
