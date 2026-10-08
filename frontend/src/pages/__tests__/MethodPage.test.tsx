import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import MethodPage from '../MethodPage'

vi.mock('../../api/client', () => ({
  itemPsychometrics: vi.fn(() => Promise.resolve({
    data: {
      spec: 'backend', randomesque: 5, answers: 0, max_share: 0,
      cuts: [
        { grade: 'junior', cut: -1.5, information: 0.4, se_after_12: 0.2 },
        { grade: 'middle', cut: -0.5, information: 0.5, se_after_12: 0.18 },
      ],
      curve: [
        { theta: -3, information: 0.1 },
        { theta: 0, information: 0.5 },
        { theta: 3, information: 0.2 },
      ],
      families: [],
      parents: [{ family_id: 'py', title: 'Python', a: 1.2, levels: [{ level: 1, b: -1 }, { level: 3, b: 0.5 }] }],
    },
  })),
}))

describe('страница методики', () => {
  it('показывает кривую, пороги грейда и пять цифр с командами', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><MethodPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    const curve = await screen.findByRole('img', { name: /Кривая информации/ })
    expect(curve.querySelectorAll('line')).toHaveLength(3)
    expect(screen.getByText('91,5 %')).toBeInTheDocument()
    expect(screen.getByText('0,47')).toBeInTheDocument()
    expect(screen.getByText('0,22')).toBeInTheDocument()
    expect(screen.getByText('0 %')).toBeInTheDocument()
    expect(screen.getByText('65,1 %')).toBeInTheDocument()
    expect(screen.getAllByText(/python -m app.validation.assessment --n 2000 --seed 7/)).toHaveLength(5)
    expect(screen.getByRole('img', { name: 'Показов ещё нет' })).toBeInTheDocument()
    expect(screen.queryByText(/item_key|правильный ответ/)).not.toBeInTheDocument()
  })
})
