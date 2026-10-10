import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import CandidateTasks from '../candidate/Tasks'

const { tasksForMe, answerTask } = vi.hoisted(() => ({ tasksForMe: vi.fn(), answerTask: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, tasksForMe, answerTask }
})

const task = {
  id: 't1', title: 'Сумма положительных', statement: 'Напишите функцию solve(xs).', answer_type: 'code',
  options: [], company: 'СибКод', addressed: false, vacancy_id: null, deadline: null, created_at: null,
  accepts_answers: true, submission: null, languages: ['python', 'javascript'],
}

describe('задания кандидата', () => {
  it('отправляет решение на выбранном языке', async () => {
    tasksForMe.mockResolvedValue({ data: [task] })
    answerTask.mockResolvedValue({ data: task })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><CandidateTasks /></MemoryRouter></QueryClientProvider>)
    await userEvent.selectOptions(await screen.findByLabelText('Язык'), 'javascript')
    const editor = screen.getByLabelText('Функция solve')
    expect(editor).toHaveAttribute('placeholder', expect.stringContaining('function solve'))
    await userEvent.type(editor, 'function solve(xs) {{ return 1 }')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить ответ' }))
    expect(answerTask).toHaveBeenCalledWith('t1', { answer_text: 'function solve(xs) { return 1 }', language: 'javascript' })
  })
})
