import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { apiError, guardianConsent } from '../api/client'
import { PageHeader } from '../components/ui'

/** The legal representative opens the link from the letter and confirms the consent. */
export default function GuardianPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [done, setDone] = useState<string | null>(null)
  const confirm = useMutation({
    mutationFn: () => guardianConsent(token).then(r => r.data as { display_name: string | null }),
    onSuccess: d => setDone(d.display_name || 'кандидата'),
  })
  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Согласие законного представителя"
        lead="Кандидату от 15 до 17 лет нужно согласие родителя или другого законного представителя на обработку персональных данных." />
      <div className="card space-y-4 text-sm">
        <p>Платформа показывает работодателям анонимную карточку: специализацию, грейд, навыки и результаты. Имя и контакты работодатель получает, только если кандидат сам примет конкретное приглашение. Отозвать согласие можно письмом оператору, карточка скроется сразу.</p>
        <p>Полный текст: <Link className="text-accent" to="/legal">документы и согласия</Link>.</p>
        {done ? (
          <p className="notice-ok" role="status">Согласие получено. Карточка {done} теперь видна работодателям.</p>
        ) : (
          <>
            <button type="button" className="btn-primary" disabled={!token || confirm.isPending} onClick={() => confirm.mutate()}>Даю согласие</button>
            {confirm.isError && <p className="notice-error" role="alert">{apiError(confirm.error, 'Ссылка недействительна')}</p>}
          </>
        )}
      </div>
    </div>
  )
}
