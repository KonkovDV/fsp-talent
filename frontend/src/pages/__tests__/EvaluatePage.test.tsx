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

async function show() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><EvaluatePage /></MemoryRouter></QueryClientProvider>)
  await userEvent.click(screen.getByRole('tab', { name: 'Загрузить JSONL' }))
}

describe('подбор на своей разметке', () => {
  it('отправляет пример и показывает метрики модели и базовой линии', async () => {
    evaluatePairs.mockResolvedValue({ data: report })
    await show()
    await userEvent.click(screen.getByRole('button', { name: 'Вставить пример' }))
    await userEvent.click(screen.getByRole('button', { name: 'Посчитать' }))
    const sent = evaluatePairs.mock.calls[0][0] as string
    expect(sent.split('\n')).toHaveLength(3)
    const table = await screen.findByTestId('evaluate-table')
    expect(within(table).getByText('Базовая линия «по резюме»')).toBeInTheDocument()
    expect(within(table).getByText('0,800')).toBeInTheDocument()
  })

  it('раскрывает таблицу по потребностям и подсвечивает, где модель хуже по P@k', async () => {
    evaluatePairs.mockResolvedValue({ data: { ...report, needs: 2, judged_needs: 2,
      per_need: [
        { need_id: 'n1', role: 'backend', grade: 'middle', judged: 3, relevant: 1, k: 3, p_at_k_model: 0.3333,
          p_at_k_resume: 0.3333, ndcg10_model: 1, ndcg10_resume: 0.8, top: [{ candidate_id: 'c1', label: 3 }] },
        { need_id: 'n2', role: 'frontend', grade: 'junior', judged: 3, relevant: 2, k: 3, p_at_k_model: 0.3333,
          p_at_k_resume: 0.6667, ndcg10_model: 0.5, ndcg10_resume: 0.9, top: [{ candidate_id: 'f3', label: 0 }] },
      ],
      paired_delta: { mean: -0.1, ci: [-0.4, 0.2], needs: 2, model_better: 1, resume_better: 1 } } })
    await show()
    await userEvent.click(screen.getByRole('button', { name: 'Вставить пример' }))
    await userEvent.click(screen.getByRole('button', { name: 'Посчитать' }))
    expect(await screen.findByTestId('paired-delta')).toHaveTextContent('−0,100')
    await userEvent.click(screen.getByText(/По потребностям \(2, модель хуже по P@k: 1\)/))
    const rows = within(screen.getByTestId('per-need-table')).getAllByRole('row')
    expect(rows).toHaveLength(3)
    expect(rows[2]).toHaveAttribute('data-lower', 'true')
    expect(rows[1]).not.toHaveAttribute('data-lower')
  })

  it('показывает причину отказа', async () => {
    evaluatePairs.mockRejectedValue({ response: { data: { error: { code: 'validation_error', message: 'Строка 1: это не JSON' } } } })
    await show()
    await userEvent.type(screen.getByLabelText(/Пары, одна на строку/), 'oops')
    await userEvent.click(screen.getByRole('button', { name: 'Посчитать' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Строка 1: это не JSON')
  })
})
