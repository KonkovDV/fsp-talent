import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, X } from 'lucide-react'
import { legalDocument, legalDocuments, type LegalDoc, type Role } from '../api/client'

/** Reads a legal document in a modal. The text is the exact version the person agrees to. */
export function LegalDocModal({ kind, onClose }: { kind: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['legal', kind], queryFn: () => legalDocument(kind).then(r => r.data),
  })
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true"
      onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[85dvh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 p-5 border-b border-gray-100">
          <div>
            <h2 className="font-bold text-lg">{data?.title ?? 'Документ'}</h2>
            {data && <p className="text-xs text-text-muted font-mono">версия {data.version} · SHA-256 {data.sha256.slice(0, 12)}…</p>}
          </div>
          <button onClick={onClose} aria-label="Закрыть" className="text-text-muted hover:text-text-primary"><X size={20} /></button>
        </div>
        <div className="p-5 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap">
          {isLoading ? 'Загрузка…' : data?.body_md.replace(/^# .*\n+/, '').replace(/\*\*/g, '')}
        </div>
      </div>
    </div>
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
        <label key={doc.kind} className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={value.includes(doc.kind)}
            onChange={e => toggle(doc.kind, e.target.checked)} data-testid={`consent-${doc.kind}`} />
          <span>
            Принимаю «{doc.title}»{' '}
            <button type="button" onClick={() => setOpen(doc.kind)}
              className="inline-flex items-center gap-1 text-fsp-violet hover:underline">
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
