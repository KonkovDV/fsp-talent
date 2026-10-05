import { useEffect, useRef, type ReactNode } from 'react'

/** A native dialog. showModal() traps focus; Escape fires cancel; a click on the backdrop closes it. */
export default function Modal({ titleId, onClose, sheet, children }: {
  titleId: string
  onClose: () => void
  sheet?: boolean
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!el.open) el.showModal()
    const onCancel = (event: Event) => { event.preventDefault(); closeRef.current() }
    el.addEventListener('cancel', onCancel)
    return () => {
      el.removeEventListener('cancel', onCancel)
      if (el.open) el.close()
    }
  }, [])
  return (
    <dialog ref={ref} aria-labelledby={titleId} className={sheet ? 'modal modal-sheet' : 'modal'}
      onClick={event => { if (event.target === event.currentTarget) onClose() }}>
      {children}
    </dialog>
  )
}
