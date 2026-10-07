import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { searchBank } from '../../api/client'
import BankGrid from '../BankGrid'

vi.mock('../../api/client', () => ({
  searchBank: vi.fn(),
}))

const bank = {
  min_cell: 5,
  cells: [
    { role: 'backend', grade: 'middle', hidden: false, candidates: 12, tested: 4 },
    { role: 'backend', grade: 'intern', hidden: true, candidates: 2, tested: 0 },
  ],
}

function renderGrid() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <BankGrid />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('витрина банка', () => {
  beforeEach(() => {
    vi.mocked(searchBank).mockResolvedValue({ data: bank } as never)
  })

  it('прячет ячейку меньше пяти и ведёт видимую в поиск с фильтрами', async () => {
    renderGrid()
    const link = await screen.findByRole('link', { name: /Backend, мидл/ })
    expect(link).toHaveAttribute('href', '/employer/search?role=backend&grade=middle')
    expect(screen.getByText('< 5')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /стажёр/ })).not.toBeInTheDocument()
    expect(screen.queryByText('2', { exact: true })).not.toBeInTheDocument()
  })

  it('пустую ячейку показывает прочерком, без ссылки', async () => {
    renderGrid()
    await screen.findByRole('link', { name: /Backend, мидл/ })
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: /Frontend/ })).not.toBeInTheDocument()
  })
})
