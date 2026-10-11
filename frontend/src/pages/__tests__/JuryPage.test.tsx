import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuryPage from '../JuryPage'

vi.mock('../../api/client', () => ({
  apiError: (_e: unknown, f: string) => f,
  askPublicGuide: vi.fn(),
  categoryRanking: vi.fn(),
  telegramAchievements: vi.fn(),
  telegramVacancies: vi.fn(),
}))

describe('JuryPage маршрут ТЗ 3.3', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('показывает 8 шагов сквозного сценария со ссылками Открыть', () => {
    render(<MemoryRouter><JuryPage /></MemoryRouter>)
    const section = screen.getByTestId('jury-scenario-33')
    expect(section).toBeInTheDocument()
    for (let n = 1; n <= 8; n++) {
      expect(screen.getByTestId(`scenario-done-${n}`)).toBeInTheDocument()
    }
    const opens = screen.getAllByRole('link', { name: 'Открыть' })
    expect(opens.length).toBeGreaterThanOrEqual(8)
  })

  it('отмечает шаг готовым в localStorage', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><JuryPage /></MemoryRouter>)
    await user.click(screen.getByTestId('scenario-done-1'))
    expect(localStorage.getItem('fsp-jury-scenario-33:1')).toBe('1')
    expect(screen.getByText('готово')).toBeInTheDocument()
  })

  it('помечает пробный экспресс как не ставящий грейд', () => {
    render(<MemoryRouter><JuryPage /></MemoryRouter>)
    expect(screen.getByText(/Пробный экспресс-тест грейд не ставит/)).toBeInTheDocument()
  })
})
