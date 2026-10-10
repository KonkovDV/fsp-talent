import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Heart } from 'lucide-react'
import { apiError } from '../../api/client'
import CandidateCard from '../../components/CandidateCard'
import InviteDialog from '../../components/InviteDialog'
import TaskDialog from '../../components/TaskDialog'
import { Empty, PageHeader, Skeleton, plural } from '../../components/ui'
import { useFavorites } from '../../hooks/useFavorites'

/** Cards the company saved from search or need matches, newest first. */
export default function EmployerFavorites() {
  const fav = useFavorites()
  const [inviteFor, setInviteFor] = useState<string | null>(null)
  const [taskFor, setTaskFor] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const data = fav.query.data
  const items = data?.items ?? []

  return (
    <div className="space-y-6">
      <PageHeader title="Избранное"
        lead="Карточки, отмеченные в поиске и в подборе по потребностям. Они анонимны, как в поиске. Кто скрыл профиль или перестал искать работу, из списка уходит." />
      {sent && <p className="text-sm text-ok" role="status">Приглашение отправлено.</p>}
      {(fav.query.isError || fav.error) && <p className="text-sm text-danger" role="alert">{apiError(fav.query.error ?? fav.error)}</p>}
      {fav.query.isLoading && <Skeleton />}
      {data && data.hidden > 0 && (
        <p className="text-sm text-ink-2" data-testid="favorites-hidden">
          {data.hidden} {plural(data.hidden, ['карточка скрыта', 'карточки скрыты', 'карточек скрыто'])}: кандидат убрал профиль из поиска.
        </p>
      )}
      {data && items.length === 0 && (
        <Empty title="В избранном пусто" icon={<Heart size={18} />}
          action={<Link to="/employer/search" className="btn-secondary btn-sm">Открыть поиск</Link>}>
          Нажмите «В избранное» на карточке кандидата.
        </Empty>
      )}
      <div className="space-y-4">
        {items.map(card => (
          <CandidateCard key={card.candidate_id} card={card} onOffer={setInviteFor} onTask={setTaskFor}
            favorite={{ on: true, toggle: fav.toggle }} />
        ))}
      </div>
      {taskFor && <TaskDialog candidateId={taskFor} onClose={() => setTaskFor(null)} />}
      {inviteFor && <InviteDialog candidateId={inviteFor} defaultRole=""
        onClose={() => setInviteFor(null)} onSent={() => setSent(true)} />}
    </div>
  )
}
