import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import CandidateCard, { claimBoundary, skillProvenance, type CandidateCardData } from '../CandidateCard'

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
  it('отличает навык без проверки тестом от отсутствующего', async () => {
    render(<CandidateCard card={{
      ...card,
      match: {
        ...card.match!,
        reasons: [
          { code: 'SKILL_UNTESTED', text: 'Заявлены, тестом не подтверждены: PostgreSQL', tone: 'info', source: 'заявлено' },
          { code: 'SKILL_GAP', text: 'Нет навыков: Go', tone: 'minus', source: 'заявлено' },
        ],
      },
    }} onOffer={() => undefined} />)
    await userEvent.click(screen.getByRole('button', { name: /Почему в выдаче/ }))
    const text = screen.getByTestId('match').textContent ?? ''
    expect(text).toContain('Тестом не подтверждён · заявлено')
    expect(text).toContain('Нет навыка')
    expect(text).not.toContain('SKILL_UNTESTED')
  })

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

  it('помечает подтверждённый грейд на границе уровня и не прячет его', () => {
    render(<CandidateCard card={{ ...card, grade_borderline: true, match: undefined }} onOffer={() => undefined} />)
    expect(screen.getByText('Грейд подтверждён тестом')).toBeInTheDocument()
    expect(screen.getByText('на границе уровня')).toBeInTheDocument()
  })

  it('без пометки границы не пишет её', () => {
    render(<CandidateCard card={{ ...card, match: undefined }} onOffer={() => undefined} />)
    expect(screen.queryByText('на границе уровня')).not.toBeInTheDocument()
  })

  it('граница утверждения: заявленный грейд прямо назван неподтверждённым', () => {
    const b = claimBoundary({ grade: 'middle', grade_source: 'declared' }, false)
    expect(b.yes).toEqual([])
    expect(b.no[0]).toMatch(/заявлен кандидатом/)
  })

  it('граница утверждения: тест и ФСП подтверждают своё, опыт — нет', () => {
    const b = claimBoundary({ grade: 'senior', grade_source: 'assessed', grade_borderline: true }, true)
    expect(b.yes.join(' ')).toMatch(/Тест.*на границе уровня/)
    expect(b.yes.join(' ')).toMatch(/ФСП/)
    expect(b.no.join(' ')).toMatch(/опыт коммерческой разработки/)
    render(<CandidateCard card={{ ...card, match: undefined }} onOffer={() => undefined} />)
    expect(screen.getByText('Что подтверждено и что нет')).toBeInTheDocument()
  })

  it('у подтверждённого навыка есть источник, дата и методика; без поля API — ничего', () => {
    const card2 = { skill_provenance: { Python: { source: 'test_confirmed', verified_at: '2026-10-01', method_version: 'test/cat-3pl' } } }
    expect(skillProvenance('Python', card2)).toBe('Источник: тест, 2026-10-01; методика test/cat-3pl')
    expect(skillProvenance('Go', card2)).toBeUndefined()
    expect(skillProvenance('Python', {})).toBeUndefined()
  })

  it('показывает Algorithms по-русски как Алгоритмы', () => {
    render(<CandidateCard card={{
      ...card,
      matched_skills: ['Algorithms'],
      stack: ['Algorithms'],
      skill_evidence: { Algorithms: 'test_confirmed' },
      match: undefined,
    }} onOffer={() => undefined} />)
    expect(screen.getByText('Алгоритмы, подтверждён')).toBeInTheDocument()
    expect(screen.queryByText(/Algorithms/)).not.toBeInTheDocument()
  })

})
