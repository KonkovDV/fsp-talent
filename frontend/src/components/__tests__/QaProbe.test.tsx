import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import QaProbe from '../QaProbe'

vi.mock('../../api/client', () => ({
  apiError: () => 'ошибка',
  submitQaProbe: vi.fn(() => Promise.resolve({
    data: {
      accepted: 3, rejected: 0, mutants: 4, grade_unchanged: true,
      killed: ['нет нижней границы', 'нет верхней границы', 'всегда ноль', 'сдвиг на единицу'],
    },
  })),
}))

describe('практическая проверка QA', () => {
  it('показывает пойманные дефекты и не обещает смену грейда', async () => {
    const user = userEvent.setup()
    render(<QaProbe />)
    await user.type(screen.getByLabelText('Вход 1'), '-1')
    await user.type(screen.getByLabelText('Ожидание 1'), '0')
    await user.click(screen.getByRole('button', { name: 'Проверить пары' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Пойманы дефекты: нет нижней границы')
    expect(screen.getByRole('status')).toHaveTextContent('Грейд не изменился')
  })
})