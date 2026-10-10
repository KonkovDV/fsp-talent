import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import GuideBox from '../GuideBox'

vi.mock('../../api/client', () => ({
  askGuide: vi.fn().mockResolvedValue({
    data: {
      answer: 'Грейд подтверждается в разделе «Тест на грейд».',
      links: [
        { label: 'Тест на грейд', to: '/candidate/assessment' },
        { label: 'Чужое', to: '/employer/moderation' },
      ],
    },
  }),
  apiError: () => 'ошибка',
}))

describe('подсказка по разделам', () => {
  it('показывает только ссылку своей роли', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><GuideBox role="participant" /></MemoryRouter>
      </QueryClientProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Куда нажать' }))
    await userEvent.type(screen.getByLabelText('Вопрос остаётся на сервере'), 'где грейд')
    await userEvent.click(screen.getByRole('button', { name: 'Показать раздел' }))
    expect(await screen.findByRole('link', { name: 'Тест на грейд' })).toHaveAttribute('href', '/candidate/assessment')
    expect(screen.queryByRole('link', { name: 'Чужое' })).not.toBeInTheDocument()
  })
})