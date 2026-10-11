import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import LeaderboardPage from '../LeaderboardPage'

const { getLeaderboard } = vi.hoisted(() => ({ getLeaderboard: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, getLeaderboard }
})

const row = (rank: number) => ({
  rank, display_name: `Участник 00${rank}A`, region: 'Казань', discipline: 'algorithmic', label: 'Алгоритмическое',
  best_rank: 'КМС', grade: 'middle', lcb: 1 - rank / 10,
})

describe('рейтинг без имён (ST-03)', () => {
  it('строки не ведут на публичную страницу с именем', async () => {
    getLeaderboard.mockResolvedValue({ data: [row(1), row(2), row(3), row(4)] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter><LeaderboardPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    expect((await screen.findAllByText('Участник 004A')).length).toBeGreaterThan(0)
    expect(container.querySelector('a[href^="/p/"]')).toBeNull()
  })
})
