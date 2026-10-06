import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { apiError, fspCallback } from '../../api/client'
import { PageHeader } from '../../components/ui'

/** Return from FSP ID: the server exchanges the code, verifies the ID token and loads the protocols. */
export default function FspCallback() {
  const [params] = useSearchParams()
  const qc = useQueryClient()
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null)
  const sent = useRef(false)

  useEffect(() => {
    const code = params.get('code'), st = params.get('state')
    if (sent.current) return
    sent.current = true
    if (!code || !st) { setState({ ok: false, text: 'В ответе ФСП ID нет кода. Начните привязку заново.' }); return }
    fspCallback(code, st)
      .then(r => {
        qc.invalidateQueries({ queryKey: ['myProfile'] })
        setState({ ok: true, text: `ФСП ID ${r.data.fsp_id} привязан, загружено протоколов: ${r.data.results}.` })
      })
      .catch(e => setState({ ok: false, text: apiError(e, 'Привязать ФСП ID не удалось') }))
  }, [params, qc])

  return (
    <div className="max-w-xl">
      <PageHeader title="Привязка ФСП ID" />
      {!state && <p className="text-sm text-ink-2" role="status">Проверяем ответ ФСП ID…</p>}
      {state && <p className={state.ok ? 'notice-ok' : 'notice-error'} role={state.ok ? 'status' : 'alert'}>{state.text}</p>}
      {state && <Link to={state.ok ? '/candidate/results' : '/candidate/profile'} className="btn-primary mt-4 inline-flex">
        {state.ok ? 'Посмотреть результаты' : 'Вернуться в профиль'}</Link>}
    </div>
  )
}
