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
  it('складывает вклады полос в оценку работодателя', () => {
    const summed: CandidateCardData = {
      ...card,
      match: {
        score: 0.4,
        employer: 0.45,
        accept: 0.8,
        congestion: 0,
        plus: [], minus: [], info: [],
        factors: [
          { key: 'skills', label: 'Навыки', weight: 0.5, value: 1, contrib: 0.2 },
          { key: 'grade', label: 'Грейд', weight: 0.3, value: 1, contrib: 0.15 },
          { key: 'test', label: 'Тест', weight: 0.5, value: 0.4, contrib: 0.1 },
        ],
      },
    }
    render(<CandidateCard card={{
      ...summed,
      match: { ...summed.match!, reply: { p: 0.87, label: 'высокая' } },
    }} onOffer={() => undefined} />)
    expect(screen.getByTestId('reply-chance')).toHaveTextContent('Ответят: высокая, 87 %')
    const shares = screen.getAllByTestId('factor-share').map(node => Number(node.textContent))
    const employer = Number(screen.getByTestId('employer-score').textContent?.replace('Работодатель ', ''))
    expect(shares.reduce((sum, part) => sum + part, 0)).toBeCloseTo(employer, 5)
    expect(screen.getByText(/гармоническое среднее/)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Навыки 100/ })).toBeInTheDocument()
    expect(screen.getByTestId('candidate-card').textContent).not.toMatch(/@|Ирина/)
  })

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
