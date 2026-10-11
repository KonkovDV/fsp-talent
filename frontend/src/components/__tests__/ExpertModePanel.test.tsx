import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExpertModePanel from '../ExpertModePanel'

const { simulateAssessment } = vi.hoisted(() => ({ simulateAssessment: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, simulateAssessment }
})

const step = (n: number, correct: boolean) => ({
  n, family: 'SQL: результат запроса', topic: 'sql', level: 3, difficulty: -0.2, correct, theta: 0.1, se: 0.5, p_pass: 0.9,
})
const run = (earned: string | null, seed: number) => ({
  spec: 'backend', theta: 0, true_grade: 'middle', target: 'middle', cut: -0.5, seed,
  steps: [step(1, true), step(2, false)], items: 2, max_items: 20, stop_reason: 'решение принято',
  theta_hat: 0.1, se: 0.5, p_pass: 0.9, passed: earned === 'middle', earned,
})

beforeEach(() => simulateAssessment.mockReset())

describe('режим эксперта (JS-02)', () => {
  it('показывает задания по шагам, итоговый грейд и совпадение на повторе', async () => {
    simulateAssessment.mockResolvedValueOnce({ data: run('middle', 1) }).mockResolvedValueOnce({ data: run('junior', 2) })
    render(<ExpertModePanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Запустить тест' }))
    expect(simulateAssessment).toHaveBeenCalledWith({ spec: 'backend', grade: 'middle' })
    expect(await screen.findByTestId('expert-run')).toHaveTextContent('грейд мидл')
    expect(screen.getAllByRole('row')).toHaveLength(3)
    expect(screen.getByText('неверно')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Повторить на новых заданиях' }))
    expect(await screen.findByRole('status')).toHaveTextContent('грейд не совпал')
  })

  it('пакет из 50 прогонов показывает долю совпадений', async () => {
    simulateAssessment.mockResolvedValueOnce({ data: run('middle', 1) }).mockResolvedValueOnce({
      data: { ...run('middle', 3), batch: { n: 50, same_as_first: 0.72, same_as_truth: 0.7, passed: 0.72, median_items: 14, grades: { middle: 36, junior: 14 } } },
    })
    render(<ExpertModePanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Запустить тест' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Ещё 50 прогонов' }))
    expect(simulateAssessment).toHaveBeenLastCalledWith({ spec: 'backend', grade: 'middle', batch: 50 })
    expect(await screen.findByTestId('expert-batch')).toHaveTextContent('72 %')
  })
})
