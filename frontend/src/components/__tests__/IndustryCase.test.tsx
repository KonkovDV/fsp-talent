import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import IndustryCase from '../IndustryCase'

vi.mock('../../api/client', () => ({
  industryCase: vi.fn(),
}))

import { industryCase } from '../../api/client'

describe('IndustryCase', () => {
  it('shows the plot only after the button and reports the shared rubric', async () => {
    vi.mocked(industryCase)
      .mockResolvedValueOnce({ data: {
        label: 'Финансы и финтех', title: 'Комиссия перевода',
        plot: 'Комиссия 1 % суммы, но не меньше 30.',
        ask: 'Какая комиссия с 10 000?', follow: 'Сумма стала 2 000. Какая теперь комиссия?',
      } } as never)
      .mockResolvedValueOnce({ data: { rubric: 'оба ответа сошлись с рубрикой', grade_unchanged: true } } as never)
    const user = userEvent.setup()
    render(<IndustryCase />)
    expect(screen.queryByText(/Комиссия 1/)).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Показать кейс' }))
    expect(screen.getByText(/Комиссия 1/)).toBeTruthy()
    await user.type(screen.getByLabelText(/Какая комиссия/), '100')
    await user.type(screen.getByLabelText(/Сумма стала/), '30')
    await user.click(screen.getByRole('button', { name: 'Проверить' }))
    expect(await screen.findByRole('status')).toHaveTextContent('оба ответа сошлись с рубрикой')
  })
})
