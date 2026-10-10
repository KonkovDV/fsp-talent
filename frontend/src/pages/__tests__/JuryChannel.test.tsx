import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuryPage from '../JuryPage'

const { telegramAchievements, telegramVacancies } = vi.hoisted(() => ({
  telegramAchievements: vi.fn(),
  telegramVacancies: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, telegramAchievements, telegramVacancies }
})

beforeEach(() => {
  telegramAchievements.mockResolvedValue({ data: { text: 'ФСП ID FSP001\nГрейд этим списком не ставится.' } })
  telegramVacancies.mockResolvedValue({ data: { text: 'Открытые вакансии\nИмён кандидатов здесь нет.' } })
})

describe('канал без кабинета', () => {
  it('показывает протоколы по ФСП ID и не ставит грейд', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><JuryPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Протоколы' }))
    expect(telegramAchievements).toHaveBeenCalledWith('FSP001')
    expect(await screen.findByRole('status')).toHaveTextContent('не ставится')
  })
})
