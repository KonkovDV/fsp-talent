import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import EmployerFavorites from '../employer/Favorites'

const { get, put } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, listFavorites: get, setFavorite: put }
})

const card = {
  candidate_id: 'c1', role: 'backend', grade: 'middle', grade_source: 'assessed', region: 'Новосибирск',
  experience_years: 3, stack: ['Python'], matched_skills: [], missing_skills: [], disciplines: [], why: [],
  saved_at: '2026-10-10T09:00:00Z',
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><EmployerFavorites /></MemoryRouter></QueryClientProvider>)
}

describe('избранное работодателя', () => {
  it('показывает сохранённые карточки, считает скрытые и снимает отметку', async () => {
    get.mockResolvedValue({ data: { items: [card], ids: ['c1'], hidden: 2, max: 200 } })
    put.mockResolvedValue({ data: { candidate_id: 'c1', favorite: false } })
    show()
    expect(await screen.findByTestId('candidate-card')).toHaveAttribute('data-candidate-id', 'c1')
    expect(screen.getByTestId('favorites-hidden')).toHaveTextContent('2 карточки скрыты')
    const toggle = screen.getByTestId('favorite-toggle')
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(toggle)
    await waitFor(() => expect(put).toHaveBeenCalledWith('c1', false))
  })

  it('пустое избранное ведёт в поиск', async () => {
    get.mockResolvedValue({ data: { items: [], ids: [], hidden: 0, max: 200 } })
    show()
    expect(await screen.findByText('В избранном пусто')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Открыть поиск' })).toHaveAttribute('href', '/employer/search')
  })
})
