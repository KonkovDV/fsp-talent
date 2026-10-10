import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import EvaluatePage from '../EvaluatePage'

const { evaluatePairs } = vi.hoisted(() => ({ evaluatePairs: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, evaluatePairs }
})

const report = {
  pairs: 3, needs: 1, judged_needs: 1, sha256: 'a'.repeat(64),
  rows: [
    { method: 'full', title: 'ФСП Талант: оценка соответствия', ndcg10: 1, ndcg_ci: [1, 1], p10: 0.3333, map: 1 },
    { method: 'keyword', title: 'Базовая линия «по резюме»', ndcg10: 0.8, ndcg_ci: null, p10: 0.3333, map: 0.5 },
  ],
}

function show() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><EvaluatePage /></MemoryRouter></QueryClientProvider>)
}

describe('подбор на своей разметке', () => {
  it('отправляет пример и показывает метрики модели и базовой линии', async () => {
    evaluatePairs.mockResolvedValue({ data: report })
    show()
    await userEvent.click(screen.getByRole('button', { name: 'Вставить пример' }))
    await userEvent.click(screen.getByRole('button', { name: 'Посчитать' }))
    const sent = evaluatePairs.mock.calls[0][0] as string
    expect(sent.split('\n')).toHaveLength(3)
    const table = await screen.findByTestId('evaluate-table')
    expect(within(table).getByText('Базовая линия «по резюме»')).toBeInTheDocument()
    expect(within(table).getByText('0,800')).toBeInTheDocument()
  })

  it('показывает причину отказа', async () => {
    evaluatePairs.mockRejectedValue({ response: { data: { error: { code: 'validation_error', message: 'Строка 1: это не JSON' } } } })
    show()
    await userEvent.type(screen.getByLabelText(/Пары, одна на строку/), 'oops')
    await userEvent.click(screen.getByRole('button', { name: 'Посчитать' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Строка 1: это не JSON')
  })
})
