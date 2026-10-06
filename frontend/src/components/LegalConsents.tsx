import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, X } from 'lucide-react'
import { legalDocument, legalDocuments, type LegalDoc, type Role } from '../api/client'
import Modal from './Modal'

/** Reads a legal document in a modal. The text is the exact version the person agrees to. */
export function LegalDocModal({ kind, onClose }: { kind: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['legal', kind], queryFn: () => legalDocument(kind).then(r => r.data),
  })
  return (
    <Modal titleId="legal-title" onClose={onClose}>
      <div className="flex max-h-[85dvh] w-full flex-col rounded-xl border border-line bg-panel shadow-pop">
        <div className="flex items-start justify-between gap-4 border-b border-line p-5">
          <div>
            <h2 id="legal-title" className="font-display text-lg font-bold text-ink">{data?.title ?? 'Документ'}</h2>
            {data && <p className="font-mono text-xs text-ink-3">версия {data.version}, SHA-256 {data.sha256.slice(0, 12)}…</p>}
          </div>
          <button onClick={onClose} aria-label="Закрыть" className="btn-ghost h-8 w-8 p-0"><X size={18} /></button>
        </div>
        <div className="overflow-y-auto whitespace-pre-wrap p-5 text-sm leading-relaxed text-ink">
          {isLoading ? 'Загрузка…' : data?.body_md.replace(/^# .*\n+/, '').replace(/\*\*/g, '')}
        </div>
      </div>
    </Modal>
  )
}

/**
 * Checkboxes for the documents a role must accept. 152-FZ art. 9: consent to personal data processing
 * is a separate document, so each one has its own box; nothing is pre-ticked.
 */
export function ConsentChecklist({ role, value, onChange }: {
  role: Role; value: string[]; onChange: (kinds: string[]) => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const { data: docs = [] } = useQuery({
    queryKey: ['legal-list', role], queryFn: () => legalDocuments(role).then(r => r.data),
  })
  const required = docs.filter((d: LegalDoc) => d.required)
  const toggle = (kind: string, on: boolean) =>
    onChange(on ? [...new Set([...value, kind])] : value.filter(k => k !== kind))
  return (
    <div className="space-y-2">
      {required.map(doc => (
        <label key={doc.kind} className="flex items-start gap-2.5 text-sm text-ink">
          <input type="checkbox" className="mt-1" checked={value.includes(doc.kind)}
            onChange={e => toggle(doc.kind, e.target.checked)} data-testid={`consent-${doc.kind}`} />
          <span>
            Принимаю «{doc.title}»{' '}
            <button type="button" onClick={() => setOpen(doc.kind)}
              className="inline-flex items-center gap-1 text-accent hover:underline">
              <FileText size={12} />прочитать
            </button>
          </span>
        </label>
      ))}
      {open && <LegalDocModal kind={open} onClose={() => setOpen(null)} />}
    </div>
  )
}

export function requiredKinds(docs: LegalDoc[] | undefined): string[] {
  return (docs ?? []).filter(d => d.required).map(d => d.kind)
}
