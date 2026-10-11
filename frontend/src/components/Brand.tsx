import { Link } from 'react-router-dom'
import mark from '../assets/mark.webp'

/** Product mark from the logo (docs/assets/logo.png): the runner between code brackets. Reads on light and dark. */
export function BrandMark({ size = 32, tile = false }: { size?: number; tile?: boolean }) {
  const img = <img src={mark} width={size} height={size} alt="" aria-hidden className="shrink-0 select-none" draggable={false} />
  if (!tile) return img
  return <span className="grid shrink-0 place-items-center rounded-lg bg-white p-1 shadow-sm">{img}</span>
}

export function Brand({ to = '/', compact = false }: { to?: string; compact?: boolean }) {
  return (
    <Link to={to} className="-m-1 flex items-center gap-2.5 rounded-lg p-1" aria-label="ФСП Талант · команда Дмитрия Конькова — на главную">
      <BrandMark />
      {!compact && (
        <span className="leading-none">
          <span className="block font-display text-[15px] font-extrabold tracking-[-0.02em] text-ink">ФСП Талант</span>
          <span className="block pt-1 text-2xs text-ink-3">команда Дмитрия Конькова</span>
        </span>
      )}
    </Link>
  )
}
