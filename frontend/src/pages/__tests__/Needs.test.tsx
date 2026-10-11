import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EmployerNeeds from '../employer/Needs'

const { listNeeds, getNeed, updateNeed, createNeed, restoreNeed, needMatches, needShortlist } = vi.hoisted(() => ({
  listNeeds: vi.fn(),
  getNeed: vi.fn(),
  updateNeed: vi.fn(),
  createNeed: vi.fn(),
  restoreNeed: vi.fn(),
  needMatches: vi.fn(),
  needShortlist: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    listNeeds, getNeed, updateNeed, createNeed, restoreNeed,
    surveyOptions: vi.fn(() => Promise.resolve({ data: { specializations: { backend: 'Бэкенд' }, grades: ['middle'], industries: {} } })),
    needMatches,
    needShortlist,
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
  needMatches.mockResolvedValue({ data: { items: [], recommended_categories: [] } })
  needShortlist.mockResolvedValue({ data: { items: [], funnel: { shortlisted: 0, invited: 0, rejected: 0 } } })
})

describe('потребность', () => {
  it('готовая потребность заполняет форму и сама её не сохраняет', async () => {
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('button', { name: 'Новая потребность' }))
    await userEvent.click(screen.getByRole('button', { name: 'Высокая нагрузка' }))
    expect(screen.getByLabelText('Название')).toHaveValue('Сервис под нагрузкой')
    expect(screen.getByLabelText('Обязательные навыки')).toHaveValue('Go, PostgreSQL, Kafka')
    expect(createNeed).not.toHaveBeenCalled()
  })

  it('кнопка-пример вставляет текст вакансии и ничего не сохраняет', async () => {
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('button', { name: 'Новая потребность' }))
    await userEvent.click(screen.getByRole('button', { name: 'Frontend, senior' }))
    expect(screen.getByLabelText('Текст вакансии')).toHaveValue('Frontend-разработчик Senior: React, TypeScript, JavaScript, CSS. Удалённо.')
    expect(createNeed).not.toHaveBeenCalled()
  })

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

  it('шорт-лист можно сузить до одного шага воронки', async () => {
    needShortlist.mockResolvedValue({ data: {
      funnel: { shortlisted: 2, invited: 1, rejected: 0 },
      items: [{ candidate_id: 'c1', role: 'backend', grade: 'middle', score: 0.8, picked_on_version: 2, added_at: '2026-01-01T00:00:00Z', status: 'invited' }],
    } })
    renderPage(<EmployerNeeds />)
    await userEvent.click(await screen.findByRole('tab', { name: /Шорт-лист/ }))
    expect(screen.getByText('Отобрано 2, приглашено 1, отказ 0.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Приглашено 1' }))
    expect(needShortlist).toHaveBeenCalledWith('need-1', 'invited')
  })

  it('показывает, сколько условий оставили из банка', async () => {
    needMatches.mockResolvedValue({ data: { items: [], total: 12, base_total: 60, recommended_categories: [] } })
    renderPage(<EmployerNeeds />)
    expect(await screen.findByText('По условиям этой потребности 12 из 60 в банке.')).toBeInTheDocument()
  })

  it('не предлагает вернуть единственную версию', async () => {
    getNeed.mockResolvedValue({ data: { ...need, version: 1, versions: [{ version: 1, params: need.params }] } })
    listNeeds.mockResolvedValue({ data: [{ ...need, version: 1 }] })
    renderPage(<EmployerNeeds />)
    expect(await screen.findByRole('heading', { name: 'Платёжный бэкенд' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Вернуть версию/ })).not.toBeInTheDocument()
  })
})
