import type { ReactNode } from 'react'

/** JS-01: plain words on the page, the professional term in the tooltip (mouse and keyboard focus). */
export default function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <abbr title={`Термин: ${term}`} tabIndex={0} className="cursor-help no-underline decoration-dotted underline-offset-2 hover:underline focus:underline">
      {children}
    </abbr>
  )
}
