import { useQuery } from '@tanstack/react-query'
import { getMyEmployerOffers } from '../../api/client'
import { Link } from 'react-router-dom'
import { Search, Send } from 'lucide-react'

export default function EmployerDashboard() {
  const { data: offers = [] } = useQuery({
    queryKey: ['empOffers'], queryFn: () => getMyEmployerOffers().then(r => r.data)
  })
  const pending = offers.filter((o: { status: string }) => o.status === 'pending').length
  const accepted = offers.filter((o: { status: string }) => o.status === 'accepted').length
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Кабинет работодателя</h1>
      <div className="grid sm:grid-cols-2 gap-4">
        <Link to="/employer/search" className="card-hover flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-fsp-violet flex items-center justify-center">
            <Search size={22} className="text-white" />
          </div>
          <div>
            <p className="font-semibold">Поиск кандидатов</p>
            <p className="text-sm text-gray-500">Анонимные карточки, фильтр по роли, грейду и разряду</p>
          </div>
        </Link>
        <Link to="/employer/offers" className="card-hover flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-fsp-red flex items-center justify-center">
            <Send size={22} className="text-white" />
          </div>
          <div>
            <p className="font-semibold">Мои офферы</p>
            <p className="text-sm text-gray-500">{pending} ожидают · {accepted} приняты</p>
          </div>
        </Link>
      </div>
    </div>
  )
}
