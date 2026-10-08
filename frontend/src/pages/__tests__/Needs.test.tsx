import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployerNeeds from '../employer/Needs'

const { listNeeds, getNeed, updateNeed, createNeed, restoreNeed } = vi.hoisted(() => ({
  listNeeds: vi.fn(),
  getNeed: vi.fn(),
  updateNeed: vi.fn(),
  createNeed: vi.fn(),
  restoreNeed: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    listNeeds, getNeed, updateNeed, createNeed, restoreNeed,
    surveyOptions: vi.fn(() => Promise.resolve({ data: { specializations: { backend: 'Бэкенд' }, grades: ['middle'], industries: {} } })),
    needMatches: vi.fn(() => Promise.resolve({ data: { items: [], recommended_categories: [] } })),
    needShortlist: vi.fn(() => Promise.resolve({ data: { items: [] } })),
    compareNeed: vi.fn(),
    needExam: vi.fn(),
    setShortlist: vi.fn(),
    removeShortlist: vi.fn(),
  }
})

const need = {
  id: 'need-1', title: 'Платёжный бэкенд', version: 2, shortlist_count: 1,
  params: { role: 'backend', grade: 'middle', skills: ['Python'], nice_to_have: [], industry: null, work_goal: null, salary_from: 180000, salary_to: 240000 },
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
  listNeeds.mockResolvedValue({ data: [need] })
  getNeed.mockResolvedValue({ data: { ...need, versions: [{ version: 1, params: need.params }, { version: 2, params: need.params }] } })
  updateNeed.mockResolvedValue({ data: { ...need, version: 3 } })
  createNeed.mockResolvedValue({ data: { ...need, id: 'need-2', version: 1, title: 'Новая' } })
  restoreNeed.mockResolvedValue({ data: { ...need, version: 1 } })
})

describe('потребность', () => {
  it('короткое название не создаёт потребность', async () => {
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('button', { name: 'Новая потребность' }))
    await userEvent.type(screen.getByLabelText('Название'), 'А')
    expect(screen.getByRole('button', { name: 'Создать' })).toBeDisabled()
    expect(createNeed).not.toHaveBeenCalled()
  })

  it('сохраняет изменение новой версией', async () => {
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('button', { name: 'Изменить' }))
    expect(screen.getByRole('heading', { name: 'Изменение — будет сохранено новой версией' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить новую версию' }))
    expect(updateNeed).toHaveBeenCalledWith('need-1', expect.objectContaining({
      title: 'Платёжный бэкенд',
      expected_version: 2,
    }))
  })

  it('возвращает прошлую версию', async () => {
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('button', { name: 'Вернуть версию 1' }))
    expect(restoreNeed).toHaveBeenCalledWith('need-1', 1)
  })

  it('не предлагает вернуть единственную версию', async () => {
    getNeed.mockResolvedValue({ data: { ...need, version: 1, versions: [{ version: 1, params: need.params }] } })
    listNeeds.mockResolvedValue({ data: [{ ...need, version: 1 }] })
    renderPage(<EmployerNeeds />)
    expect(await screen.findByRole('heading', { name: 'Платёжный бэкенд' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Вернуть версию/ })).not.toBeInTheDocument()
  })
})
