import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getMyEmployerOffers, getOfferContacts, withdrawOffer } from '../../api/client'

const STATUS: Record<string, string> = {
  pending: 'ожидает', accepted: 'принят', rejected: 'отклонён', expired: 'истёк', withdrawn: 'отозван',
}

export default function EmployerOffers() {
  const qc = useQueryClient()
  const { data: offers = [], isLoading } = useQuery({
    queryKey: ['empOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data),
  })
  const [contacts, setContacts] = useState<Record<string, string> | null>(null)
  const [error, setError] = useState('')
  const reveal = useMutation({
    mutationFn: (id: string) => getOfferContacts(id).then(r => r.data),
    onSuccess: (data) => { setError(''); setContacts(data) },
    onError: () => setError('Контакты доступны только после согласия кандидата'),
  })
  const withdraw = useMutation({
    mutationFn: withdrawOffer,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['empOffers'] }),
  })
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Мои офферы</h1>
      {isLoading && <div className="animate-pulse h-40 bg-gray-100 rounded-2xl" />}
      {error && <p className="text-sm text-fsp-red">{error}</p>}
      {offers.map((offer: Offer) => (
        <div key={offer.id} className="card flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold">{offer.role}</p>
            <p className="text-sm text-gray-500 font-mono">
              {offer.salary_from.toLocaleString('ru-RU')}–{offer.salary_to.toLocaleString('ru-RU')} {offer.currency} · {offer.work_format}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {offer.status === 'pending' && (
              <button onClick={() => withdraw.mutate(offer.id)} className="btn-secondary text-xs py-1.5">Отозвать</button>
            )}
            {offer.contacts_available && (
              <button onClick={() => reveal.mutate(offer.id)} className="btn-primary text-xs py-1.5">Контакты</button>
            )}
            <span className="badge bg-gray-100 text-gray-700">{STATUS[offer.status] ?? offer.status}</span>
          </div>
        </div>
      ))}
      {contacts && (
        <div className="card">
          <h2 className="font-semibold mb-2">Контакты: {contacts.display_name}</h2>
          <p className="text-sm">Email: {contacts.email ?? '—'}</p>
          <p className="text-sm">Telegram: {contacts.telegram ?? '—'}</p>
          <p className="text-sm">Телефон: {contacts.phone ?? '—'}</p>
          <p className="text-sm text-gray-500">{contacts.region}</p>
        </div>
      )}
      {!isLoading && offers.length === 0 && <div className="card text-center text-gray-400 py-12">Офферов пока нет</div>}
    </div>
  )
}

interface Offer {
  id: string
  role: string
  salary_from: number
  salary_to: number
  currency: string
  work_format: string
  status: string
  contacts_available: boolean
}
