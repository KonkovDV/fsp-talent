import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ItemDrafts from '../employer/ItemDrafts'

const { get, post, assessmentBlueprint } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), assessmentBlueprint: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, api: { ...actual.api, get, post }, assessmentBlueprint }
})

const draft = {
  id: 'd1', spec: 'backend', topic: 'python', level: 2, stem: 'Сколько раз выполнится цикл?', key: '6',
  status: 'pending', note: null, created_at: '2026-10-10T09:00:00Z', reviewed_at: null,
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><ItemDrafts /></QueryClientProvider>)
}

describe('черновики заданий', () => {
  it('одобряет черновик с заметкой и запрашивает новый', async () => {
    assessmentBlueprint.mockResolvedValue({ data: { specializations: { backend: { label: 'Бэкенд', topics: [{ topic: 'python', label: 'Python' }] } } } })
    get.mockResolvedValue({ data: { model_ready: true, items: [draft] } })
    post.mockResolvedValue({ data: { accepted: false, reason: 'disagree' } })
    show()
    expect(await screen.findByText('Сколько раз выполнится цикл?')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Заметка к черновику'), 'в семейство циклов')
    await userEvent.click(screen.getByRole('button', { name: 'Одобрить' }))
    expect(post).toHaveBeenCalledWith('/moderation/item-drafts/d1/review', { decision: 'approved', note: 'в семейство циклов' })
    await screen.findByRole('option', { name: 'Python' })
    await userEvent.click(screen.getByRole('button', { name: 'Запросить черновик' }))
    expect(post).toHaveBeenLastCalledWith('/moderation/item-drafts', { spec: 'backend', topic: 'python', level: 2 })
    expect(await screen.findByRole('status')).toHaveTextContent('Модели назвали разные ответы')
  })

  it('без двух моделей не даёт запросить черновик', async () => {
    assessmentBlueprint.mockResolvedValue({ data: { specializations: { backend: { label: 'Бэкенд', topics: [{ topic: 'python', label: 'Python' }] } } } })
    get.mockResolvedValue({ data: { model_ready: false, items: [] } })
    show()
    expect(await screen.findByTestId('drafts-off')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Запросить черновик' })).toBeDisabled()
  })
})
