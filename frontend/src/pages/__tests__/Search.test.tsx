import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployerSearch from '../employer/Search'

const { searchCandidates } = vi.hoisted(() => ({ searchCandidates: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    searchCandidates,
    parseQuery: vi.fn(),
    searchBank: vi.fn(() => Promise.resolve({ data: { min_cell: 5, cells: [] } })),
  }
})

const declared = {
  candidate_id: '22222222-2222-2222-2222-222222222222',
  role: 'backend', grade: 'middle', grade_source: 'declared', region: 'Казань', experience_years: 2,
  stack: ['Python'], matched_skills: ['Python'], missing_skills: [], why: [], disciplines: [],
  match: { score: 0.4, plus: [], minus: [], info: [], factors: [], reasons: [] },
}

function renderPage(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  window.matchMedia = (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => undefined, removeListener: () => undefined,
    addEventListener: () => undefined, removeEventListener: () => undefined, dispatchEvent: () => false,
  })
  searchCandidates.mockResolvedValue({ data: { total: 1, items: [declared], recommended_categories: [] } })
})

describe('поиск работодателя', () => {
  it('фильтр истории ФСП предлагает «есть» и «нет»', async () => {
    renderPage(<EmployerSearch />)
    const filter = await screen.findByRole('combobox', { name: 'История ФСП' })
    expect(screen.getByText(/Приглашение отправляет человек/)).toBeInTheDocument()
    expect(filter).toHaveDisplayValue('Не важно')
    expect(screen.getByRole('option', { name: 'Есть' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Нет' })).toBeInTheDocument()
  })

  it('отправляет фильтр «есть ФСП» только после применения', async () => {
    renderPage(<EmployerSearch />)
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'История ФСП' }), 'true')
    expect(searchCandidates).not.toHaveBeenCalledWith(expect.objectContaining({ has_fsp: 'true' }))
    await userEvent.click(screen.getByRole('button', { name: 'Применить фильтры' }))
    expect(searchCandidates).toHaveBeenLastCalledWith(expect.objectContaining({ has_fsp: 'true' }))
  })

  it('показывает, что список ещё прежний, пока фильтр не применён', async () => {
    renderPage(<EmployerSearch />)
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'История ФСП' }), 'true')
    expect(await screen.findByText(/фильтры изменены, список ещё прежний/)).toBeInTheDocument()
  })

  it('пишет, что на экране только начало длинной выдачи', async () => {
    searchCandidates.mockResolvedValue({ data: { total: 80, items: [declared], recommended_categories: [] } })
    renderPage(<EmployerSearch />)
    expect(await screen.findByText(/на экране первые 1/)).toBeInTheDocument()
  })

  it('объясняет, сколько человек точно в выбранной паре, и сколько скрыла площадка', async () => {
    searchCandidates.mockResolvedValue({ data: { total: 25, in_category: 18, platform_held: 2, items: [declared], recommended_categories: [] } })
    renderPage(<EmployerSearch />)
    expect(await screen.findByText(/кандидатов в выбранной категории, ещё 7 похожих/)).toBeInTheDocument()
    expect(screen.getByText(/Площадка не показала 2/)).toBeInTheDocument()
  })

  it('в выдаче помечает неподтверждённый грейд', async () => {
    renderPage(<EmployerSearch />)
    expect(await screen.findByText('Грейд не подтверждён')).toBeInTheDocument()
    expect(screen.queryByText('Грейд подтверждён тестом')).not.toBeInTheDocument()
  })
})
