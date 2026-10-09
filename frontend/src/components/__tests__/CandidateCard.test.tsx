import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import CandidateCard, { type CandidateCardData } from '../CandidateCard'

const card: CandidateCardData = {
  candidate_id: '11111111-1111-1111-1111-111111111111',
  role: 'backend',
  grade: 'middle',
  grade_source: 'assessed',
  region: 'Казань',
  experience_years: 3,
  stack: ['Python'],
  matched_skills: ['Python'],
  missing_skills: ['Go'],
  why: [],
  disciplines: [],
  match: {
    score: 0.82,
    plus: [],
    minus: [],
    info: [],
    factors: [],
    reasons: [
      { code: 'CATEGORY_MATCH', text: 'роль', tone: 'plus', points: 0.09 },
      { code: 'SKILL_GAP', text: 'нет Go', tone: 'minus' },
    ],
  },
}

describe('карточка кандидата', () => {
  it('показывает коды причин плашками и не печатает имя', async () => {
    render(<CandidateCard card={card} onOffer={() => undefined} />)
    await userEvent.click(screen.getByRole('button', { name: 'Почему в выдаче' }))
    const match = screen.getByText(/Категория совпала/)
    const gap = screen.getByText('Нет навыка')
    expect(match.className).toContain('badge-ok')
    expect(gap.className).toContain('badge-warn')
    expect(match.textContent).toContain('+9 к баллу')
    expect(screen.getByTestId('candidate-card').textContent).not.toMatch(/@|Ирина|Смирнова/)
  })

  it('называет дисциплину и цифру, которые вошли в балл', async () => {
    render(<CandidateCard card={{
      ...card,
      why: ['Подтверждено ФСП: Робототехника, нижняя граница 0,30 (учтено с весом 0,5), уверенность 80%, событий 2'],
    }} onOffer={() => undefined} />)
    await userEvent.click(screen.getByRole('button', { name: 'Почему в выдаче' }))
    const line = screen.getByTestId('fsp-line')
    expect(line.textContent).toContain('Робототехника')
    expect(line.textContent).toContain('0,30')
    expect(line.textContent).toContain('учтено с весом 0,5')
  })

  it('без подтверждённого грейда не пишет, что тест его дал', () => {
    render(<CandidateCard card={{ ...card, grade_source: 'declared', match: undefined }} onOffer={() => undefined} />)
    expect(screen.getByText('Грейд не подтверждён')).toBeInTheDocument()
    expect(screen.queryByText('Грейд подтверждён тестом')).not.toBeInTheDocument()
  })
})
