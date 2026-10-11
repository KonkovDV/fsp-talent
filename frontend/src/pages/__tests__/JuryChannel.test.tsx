import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuryPage from '../JuryPage'

const { telegramAchievements, telegramVacancies, categoryRanking } = vi.hoisted(() => ({
  telegramAchievements: vi.fn(),
  telegramVacancies: vi.fn(),
  categoryRanking: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, telegramAchievements, telegramVacancies, categoryRanking }
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

  it('объясняет пустой порядок порогом k-анонимности', async () => {
    categoryRanking.mockResolvedValue({ data: { total: 0, items: [], min_cell: 5, hidden: true } })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><JuryPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Показать порядок' }))
    expect(categoryRanking).toHaveBeenCalledWith('backend', 'middle')
    expect(await screen.findByText(/меньше 5 участников с публичным профилем — защита персональных данных/)).toBeInTheDocument()
  })

  it('пустую категорию не выдаёт за скрытую', async () => {
    categoryRanking.mockResolvedValue({ data: { total: 0, items: [], min_cell: 5, hidden: false } })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><JuryPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Показать порядок' }))
    expect(await screen.findByText(/пока нет участников с подтверждённым тестом грейдом/)).toBeInTheDocument()
    expect(screen.queryByText(/Скрыто/)).not.toBeInTheDocument()
  })
})
