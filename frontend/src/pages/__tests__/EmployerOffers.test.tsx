import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployerOffers from '../employer/Offers'

const { getMyEmployerOffers, offerMarket } = vi.hoisted(() => ({
  getMyEmployerOffers: vi.fn(),
  offerMarket: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, getMyEmployerOffers, offerMarket, withdrawOffer: vi.fn(), getOfferContacts: vi.fn(), advancePractice: vi.fn() }
})
vi.mock('../../components/InterviewSlots', () => ({ default: () => <div data-testid="slots" /> }))
vi.mock('../../components/CodeInterview', () => ({ default: () => <div data-testid="code-interview" /> }))
vi.mock('../../components/MessageThread', () => ({ default: () => <div /> }))

const practice = {
  id: 'offer-1', role: 'Стажёр', salary_from: 80000, salary_to: 100000, work_format: 'remote', status: 'pending',
  contacts_available: false, contact_method: null, candidate_viewed_at: null, contacts_revealed_at: null,
  created_at: '2026-10-01T10:00:00Z', expires_at: null, practice_stage: 'sent', returned_interest: true,
  candidate: { role: 'backend', grade: 'intern', grade_source: 'declared', label: null },
}
const accepted = { ...practice, id: 'offer-2', status: 'accepted', practice_stage: null, returned_interest: false, role: 'Backend' }

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><EmployerOffers /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  offerMarket.mockResolvedValue({ data: { reasons: null, salaries: [] } })
  getMyEmployerOffers.mockResolvedValue({ data: [practice, accepted] })
})

describe('приглашения работодателя', () => {
  it('показывает практику и комнату кода и в списке, и в таблице', async () => {
    show()
    expect(await screen.findAllByTestId('practice-advance')).toHaveLength(2)
    expect(screen.getAllByText('Специалист отметил интерес к компании. Имени нет.')).toHaveLength(2)
    const meetings = screen.getAllByRole('button', { name: 'Собеседование' })
    await userEvent.click(meetings[0])
    expect(screen.getAllByTestId('code-interview')).toHaveLength(2)
  })

  it('объясняет, почему рынок пуст', async () => {
    show()
    expect(await screen.findByText(/меньше пяти человек — защита персональных данных/)).toBeInTheDocument()
  })
})
