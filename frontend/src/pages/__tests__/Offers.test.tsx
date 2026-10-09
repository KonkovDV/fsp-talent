import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CandidateOffers from '../candidate/Offers'

const { getMyOffers, respondToOffer, revokeContacts } = vi.hoisted(() => ({
  getMyOffers: vi.fn(),
  respondToOffer: vi.fn(),
  revokeContacts: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, getMyOffers, respondToOffer, revokeContacts, fileComplaint: vi.fn(), updateMyProfile: vi.fn() }
})
vi.mock('../../components/InterviewSlots', () => ({ default: () => <div /> }))
vi.mock('../../components/MessageThread', () => ({ default: () => <div /> }))

const pending = {
  id: 'offer-1', company: 'Сибирский код', role: 'Backend-разработчик', contact_method: 'почта',
  salary_from: 180000, salary_to: 240000, work_format: 'remote', message: 'Команда платежей',
  status: 'pending', created_at: '2026-10-01T10:00:00Z', expires_at: '2026-10-15T10:00:00Z',
}

const accepted = { ...pending, id: 'offer-2', status: 'accepted', contacts_revoked_at: null }

function renderPage(ui: ReactNode, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  respondToOffer.mockResolvedValue({ data: {} })
  revokeContacts.mockResolvedValue({ data: {} })
})

describe('приглашения кандидата', () => {
  it('показывает вилку до вычета НДФЛ', async () => {
    getMyOffers.mockResolvedValue({ data: [pending] })
    renderPage(<CandidateOffers />)
    expect(await screen.findByText('до вычета НДФЛ')).toBeInTheDocument()
    expect(screen.getByText(/Сибирский код/)).toBeInTheDocument()
  })

  it('принимает приглашение и открывает контакты', async () => {
    getMyOffers.mockResolvedValue({ data: [pending] })
    renderPage(<CandidateOffers />)
    await userEvent.click(await screen.findByRole('button', { name: 'Принять и открыть контакты' }))
    expect(respondToOffer).toHaveBeenCalledWith('offer-1', 'accept', undefined)
  })

  it('не даёт отклонить без причины', async () => {
    getMyOffers.mockResolvedValue({ data: [pending] })
    renderPage(<CandidateOffers />)
    expect(await screen.findByRole('button', { name: 'Отклонить' })).toBeDisabled()
  })

  it('отклоняет с выбранной причиной', async () => {
    getMyOffers.mockResolvedValue({ data: [pending] })
    renderPage(<CandidateOffers />)
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Причина отказа' }), 'salary')
    await userEvent.click(screen.getByRole('button', { name: 'Отклонить' }))
    expect(respondToOffer).toHaveBeenCalledWith('offer-1', 'reject', 'salary')
  })

  it('закрывает контакты только после подтверждения', async () => {
    getMyOffers.mockResolvedValue({ data: [accepted] })
    renderPage(<CandidateOffers />)
    await userEvent.click(await screen.findByRole('button', { name: 'Закрыть контакты для этой компании' }))
    expect(revokeContacts).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Закрыть контакты' }))
    expect(revokeContacts).toHaveBeenCalledWith('offer-2')
  })

  it('открывает переписку по ссылке из уведомления', async () => {
    getMyOffers.mockResolvedValue({ data: [accepted] })
    renderPage(<CandidateOffers />, '/candidate/offers?thread=offer-2')
    expect(await screen.findByRole('button', { name: /Переписка/ })).toHaveAttribute('aria-expanded', 'true')
  })

  it('пустое состояние не показывает чужие приглашения', async () => {
    getMyOffers.mockResolvedValue({ data: [] })
    renderPage(<CandidateOffers />)
    expect(await screen.findByText('Приглашений пока нет')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Принять и открыть контакты' })).not.toBeInTheDocument()
  })
})
