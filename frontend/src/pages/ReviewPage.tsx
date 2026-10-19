import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { apiError, getGuestReview, markGuestReview, type GuestSeat } from '../api/client'
import PublicShell from '../components/PublicShell'
import { PageHeader, Skeleton } from '../components/ui'
import { ROLE_RU, gradeRu } from '../labels'

const MARKS = [
  { id: 'yes', label: 'Да' },
  { id: 'no', label: 'Нет' },
  { id: 'later', label: 'Позже' },
] as const

function Seat({ token, seat, chosen }: { token: string; seat: GuestSeat; chosen?: string }) {
  const qc = useQueryClient()
  const [error, setError] = useState('')
  const mark = useMutation({
    mutationFn: (value: 'yes' | 'no' | 'later') => markGuestReview(token, seat.seat, value),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['guestReview', token] })
    },
    onError: (e: unknown) => setError(apiError(e, 'Отметка не сохранилась')),
  })
  return (
    <article className="card space-y-3">
      <h2 className="font-display text-lg font-bold text-ink">
        Место {seat.seat}. {seat.role ? (ROLE_RU[seat.role] ?? seat.role) : 'Специализация не указана'}, {gradeRu(seat.grade)}
      </h2>
      {seat.region && <p className="text-sm text-ink-2">{seat.region}</p>}
      {seat.stack.length > 0 && <p className="text-sm text-ink">{seat.stack.join(', ')}</p>}
      {seat.why.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
          {seat.why.map(line => <li key={line}>{line}</li>)}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {MARKS.map(item => (
          <button
            key={item.id}
            type="button"
            className={chosen === item.id ? 'btn-primary btn-sm' : 'btn-secondary btn-sm'}
            aria-pressed={chosen === item.id}
            disabled={mark.isPending}
            onClick={() => mark.mutate(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {error && <p className="notice-error" role="alert">{error}</p>}
    </article>
  )
}

export default function ReviewPage() {
  const { token = '' } = useParams()
  const review = useQuery({
    queryKey: ['guestReview', token],
    enabled: token.length > 0,
    queryFn: () => getGuestReview(token).then(r => r.data),
  })
  return (
    <PublicShell>
      <PageHeader
        title={review.data?.title ?? 'Подборка'}
        lead="Имена и контакты скрыты. Отметка видна компании, которая прислала ссылку, и не двигает место в подборке."
      />
      {review.isLoading && <Skeleton className="h-48" />}
      {review.isError && <p className="notice-error" role="alert">{apiError(review.error, 'Ссылка недействительна')}</p>}
      {review.data && (
        <div className="space-y-4">
          {review.data.seats.map(seat => (
            <Seat key={seat.seat} token={token} seat={seat} chosen={review.data?.marks?.[String(seat.seat)]} />
          ))}
        </div>
      )}
    </PublicShell>
  )
}
