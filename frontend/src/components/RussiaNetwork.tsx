import data from '../assets/russia-network.json'

/**
 * The FSP brandbook's graphic language: a map of Russia and the lines that join regional branches.
 * Dots are generated from Natural Earth (public domain, world-atlas, ISC) with a conic equal-area projection;
 * nodes are regional centres joined into one network by a minimum spanning tree (frontend/scripts/gen-russia-network.mjs).
 * The lines draw once on load; with prefers-reduced-motion they are simply there.
 */
const dots = data.dots.map(([x, y]) => `M${x} ${y}h0`).join('')
const lines = data.edges.map(([a, b]) => `M${data.nodes[a].x} ${data.nodes[a].y}L${data.nodes[b].x} ${data.nodes[b].y}`).join('')

export default function RussiaNetwork({ className = '' }: { className?: string }) {
  return (
    <svg viewBox={`0 0 ${data.W} ${data.H}`} className={className} role="img"
      aria-label="Карта России: региональные отделения ФСП соединены в одну сеть">
      <path d={dots} className="stroke-line-strong" strokeWidth={3.3} strokeLinecap="round" />
      <path d={lines} className="network-line stroke-accent" strokeWidth={1.1} fill="none" pathLength={1} />
      {data.nodes.map((n, i) => (
        <circle key={n.n} cx={n.x} cy={n.y} r={n.n === 'Москва' ? 4.2 : 2.6}
          className={`network-node ${n.n === 'Москва' ? 'fill-brand-red' : 'fill-accent'}`}
          style={{ animationDelay: `${400 + i * 25}ms` }}>
          <title>{n.n}</title>
        </circle>
      ))}
    </svg>
  )
}
