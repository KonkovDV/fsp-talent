interface ScoreBarProps {
  mu: number
  lcb: number
  sigma?: number
  label?: string
  compact?: boolean
}

function scoreColor(v: number): string {
  if (v >= 0.7) return 'from-cyan-500 to-blue-400'
  if (v >= 0.5) return 'from-amber-500 to-yellow-400'
  return 'from-rose-500 to-red-400'
}

export default function ScoreBar({ mu, lcb, sigma, label, compact }: ScoreBarProps) {
  const muPct  = Math.round(mu  * 100)
  const lcbPct = Math.round(lcb * 100)

  return (
    <div className={compact ? 'space-y-1' : 'space-y-2'}>
      {label && <p className="text-xs font-medium text-text-secondary">{label}</p>}

      {/* Mu row */}
      <div className="flex items-center gap-3">
        <span className="text-2xs text-text-muted w-28 shrink-0">Байесовский скор (μ)</span>
        <div className="flex-1 score-bar-track">
          <div
            className={`score-bar-mu bg-gradient-to-r ${scoreColor(mu)}`}
            style={{ width: `${muPct}%` }}
            role="progressbar"
            aria-valuenow={muPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
        <span className="text-sm font-bold tabular w-10 text-right" style={{ color: 'oklch(0.75 0.18 200)' }}>
          {mu.toFixed(2)}
        </span>
      </div>

      {/* LCB row */}
      <div className="flex items-center gap-3">
        <span className="text-2xs text-text-muted w-28 shrink-0">Нижняя граница (LCB)</span>
        <div className="flex-1 score-bar-track">
          <div
            className="score-bar-lcb"
            style={{ width: `${lcbPct}%` }}
            role="progressbar"
            aria-valuenow={lcbPct}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
        <span className="text-sm font-bold tabular w-10 text-right text-emerald-400">
          {lcb.toFixed(2)}
        </span>
      </div>

      {sigma !== undefined && (
        <p className="text-2xs text-text-muted">σ = {sigma.toFixed(3)}</p>
      )}
    </div>
  )
}
