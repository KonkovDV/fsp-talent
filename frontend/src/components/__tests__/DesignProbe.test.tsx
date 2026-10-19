import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import DesignProbe from '../DesignProbe'

vi.mock('../../api/client', () => ({
  apiError: () => 'ошибка',
  designProbe: vi.fn((_seed: string, choice?: string) => Promise.resolve({
    data: choice
      ? { seed: 'layout-seed', matched: choice === 'контраст ниже 4,5', grade_unchanged: true }
      : {
          seed: 'layout-seed',
          grade_unchanged: true,
          lines: ['Лист 360×640.', 'Текст RGB(118, 118, 118) на фоне RGB(255, 255, 255).'],
          choices: ['контраст ниже 4,5', 'фигуры пересекаются', 'текст вне листа', 'дефекта нет'],
        },
  })),
}))

describe('макет с дефектом', () => {
  it('сверяет пометку с расчётом и не меняет грейд', async () => {
    const user = userEvent.setup()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <DesignProbe />
      </QueryClientProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Показать макет' }))
    expect(await screen.findByText(/RGB\(118, 118, 118\)/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'контраст ниже 4,5' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Грейд не изменился')
  })
})