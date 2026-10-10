import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CandidateAssessment from '../candidate/Assessment'

const { getMyProfile, assessmentBlueprint, assessmentHistory, activeAssessment, answerAssessment, noteAssessmentCopy, acceptLowerGrade } = vi.hoisted(() => ({
  acceptLowerGrade: vi.fn(),
  getMyProfile: vi.fn(),
  assessmentBlueprint: vi.fn(),
  assessmentHistory: vi.fn(),
  activeAssessment: vi.fn(),
  answerAssessment: vi.fn(),
  noteAssessmentCopy: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return {
    ...actual,
    getMyProfile,
    assessmentBlueprint,
    assessmentHistory,
    activeAssessment,
    answerAssessment,
    noteAssessmentCopy,
    acceptLowerGrade,
    saveAssessmentDraft: vi.fn(() => Promise.resolve({ data: { version: 1 } })),
    startAssessment: vi.fn(),
    abandonAssessment: vi.fn(),
    reviewAssessment: vi.fn(),
  }
})

const profile = {
  specialization: 'backend',
  grade: 'middle',
  grade_source: 'declared',
  declared_grade: 'middle',
  confirmations: [],
}

const blueprint = {
  specializations: { backend: { label: 'Бэкенд', topics: [{ topic: 'py', label: 'Python', share: 1 }] } },
  express: true,
  express_items: 15,
  express_minutes: 5,
  min_items: 8,
  max_items: 20,
  pass_probability: 0.75,
  next_test_probability: 0.9,
  code_languages: { python: 'Python' },
}

function item() {
  return {
    token: 'tok-1', seq: 3, stem: 'Сколько будет 2 + 2?', code: null, language: null,
    answer_mode: 'number' as const, options: [], topic_label: 'Арифметика', family_title: 'Сумма',
    kind: 'code', time_limit_s: 600, served_at: new Date().toISOString(),
  }
}

function session(over: Record<string, unknown> = {}) {
  return {
    session_id: 's1', status: 'in_progress', specialization: 'backend', target_grade: 'middle',
    expires_at: new Date().toISOString(),
    progress: { answered: 0, min_items: 8, max_items: 20 },
    item: item(), result: null,
    ...over,
  }
}

function result(over: Record<string, unknown> = {}) {
  return {
    outcome: 'not_passed', passed: false, upgraded: false, earned_grade: null, confirmed_grade: null,
    vacancy_test: false, recommended_grade: null, p_pass: 0.2, p_upgrade: null, theta: -0.4, se: 0.3,
    items_count: 12, score: 0.4, stop_reason: 'max_items', grade_locked_until: null, trial: false,
    note: null, confirmed_skills: [], topics: [], excluded_items: 0, person_fit: null, family_review: false,
    ...over,
  }
}

function renderPage(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  getMyProfile.mockResolvedValue({ data: profile })
  assessmentBlueprint.mockResolvedValue({ data: blueprint })
  assessmentHistory.mockResolvedValue({ data: { items: [] } })
  answerAssessment.mockResolvedValue({ data: session() })
})

describe('тест на грейд', () => {
  it('держит кнопку ответа закрытой, пока число не введено', async () => {
    activeAssessment.mockResolvedValue({ data: session() })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByLabelText('Ответ — целое число')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ответить' })).toBeDisabled()
  })

  it('после перезагрузки подставляет сохранённый ответ', async () => {
    activeAssessment.mockResolvedValue({ data: session({
      item: { ...item(), draft_text: '42', draft_version: 3 },
    }) })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByLabelText('Ответ — целое число')).toHaveValue('42')
  })

  it('не принимает буквы вместо числа', async () => {
    activeAssessment.mockResolvedValue({ data: session() })
    renderPage(<CandidateAssessment />)
    await userEvent.type(await screen.findByLabelText('Ответ — целое число'), 'сорок')
    expect(screen.getByRole('button', { name: 'Ответить' })).toBeDisabled()
    expect(answerAssessment).not.toHaveBeenCalled()
  })

  it('отправляет введённое целое число', async () => {
    activeAssessment.mockResolvedValue({ data: session() })
    renderPage(<CandidateAssessment />)
    await userEvent.type(await screen.findByLabelText('Ответ — целое число'), '42')
    await userEvent.click(screen.getByRole('button', { name: 'Ответить' }))
    expect(answerAssessment).toHaveBeenCalledWith('s1', 'tok-1', { answer_text: '42' })
  })

  it('называет группу вариантов ответа', async () => {
    activeAssessment.mockResolvedValue({ data: session({
      item: {
        ...item(),
        answer_mode: 'choice',
        options: [{ index: 0, text: 'четыре' }, { index: 1, text: 'пять' }],
      },
    }) })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByRole('radiogroup', { name: 'Варианты ответа' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'четыре' })).toBeInTheDocument()
  })

  it('показывает оставшееся время задания', async () => {
    activeAssessment.mockResolvedValue({ data: session() })
    renderPage(<CandidateAssessment />)
    const timer = await screen.findByRole('timer')
    expect(timer.getAttribute('aria-label')).toMatch(/Осталось (9|10) мин/)
  })

  it('пробный итог не подтверждает грейд', async () => {
    activeAssessment.mockResolvedValue({ data: session({
      item: null,
      progress: { answered: 15, min_items: 15, max_items: 15, p_pass: 0.2 },
      result: result({ trial: true, p_pass: 0.2 }),
    }) })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByText(/по этим ответам пока не подтвердился бы/)).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/Пробный проход/)
    expect(screen.queryByText('Уровень подтверждён')).not.toBeInTheDocument()
  })

  it('после несданного теста предлагает ступень ниже без паузы', async () => {
    activeAssessment.mockResolvedValue({ data: session({ item: null, result: result() }) })
    renderPage(<CandidateAssessment />)
    await userEvent.click(await screen.findByRole('button', { name: /тест на ступень ниже без паузы/ }))
    expect(screen.getByRole('radio', { name: /джуниор/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.queryByRole('button', { name: /тест на ступень ниже/ })).not.toBeInTheDocument()
  })

  it('предупреждает о копировании и не прерывает тест', async () => {
    noteAssessmentCopy.mockResolvedValue({ data: { copies: 1 } })
    activeAssessment.mockResolvedValue({ data: session() })
    renderPage(<CandidateAssessment />)
    await screen.findByLabelText('Ответ — целое число')
    document.dispatchEvent(new Event('copy'))
    expect(await screen.findByTestId('proctor-warn')).toHaveTextContent('Копирование текста задания записано')
    expect(screen.getByTestId('proctor-warn')).toHaveTextContent('грейд из-за этого не меняется')
    expect(screen.getByLabelText('Ответ — целое число')).toBeInTheDocument()
    expect(noteAssessmentCopy).toHaveBeenCalledWith('s1')
  })

  it('принимает ступень ниже из той же сессии', async () => {
    const offered = result({ earned_grade: 'junior', lower_offer: { grade: 'junior', p: 0.86 } })
    acceptLowerGrade.mockResolvedValue({ data: session({ item: null, status: 'completed', result: result({
      outcome: 'accepted_lower', earned_grade: 'junior', confirmed_grade: 'junior', lower_accepted: true,
    }) }) })
    activeAssessment.mockResolvedValue({ data: session({ item: null, result: offered }) })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByTestId('lower-offer')).toHaveTextContent('вероятность 86%')
    await userEvent.click(screen.getByRole('button', { name: 'Принять «джуниор»' }))
    expect(acceptLowerGrade).toHaveBeenCalledWith('s1')
    expect(await screen.findByTestId('lower-accepted')).toHaveTextContent('Грейд в профиле: джуниор')
    expect(screen.queryByTestId('lower-offer')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /тест на ступень ниже/ })).not.toBeInTheDocument()
  })

  it('у стажёра ссылки на ступень ниже нет', async () => {
    activeAssessment.mockResolvedValue({ data: session({
      item: null, target_grade: 'intern', result: result(),
    }) })
    renderPage(<CandidateAssessment />)
    expect(await screen.findByText(/Уровень «стажёр» не подтверждён/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /ступень ниже/ })).not.toBeInTheDocument()
  })
})
