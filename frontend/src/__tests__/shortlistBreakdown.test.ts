import { describe, expect, it } from 'vitest'
import { shortlistBreakdown } from '../shortlistBreakdown'
import { categoryBeats } from '../components/CandidateCard'

const card = {
  candidate_id: 'a',
  match: { factors: [
    { key: 'skills', label: 'Навыки', weight: 0.3, value: 0.7, contrib: 0.205 },
    { key: 'grade', label: 'Грейд', weight: 0.2, value: 1, contrib: 0.09 },
    { key: 'fsp', label: 'ФСП', weight: 0.1, value: null, contrib: null },
  ] },
} as never

describe('разложение в шорт-листе', () => {
  it('берёт вклады из подборки', () => {
    expect(shortlistBreakdown('a', [card])).toBe('Навыки 20,5 · Грейд 9,0')
  })
  it('пусто, если кандидата нет в загруженной подборке', () => {
    expect(shortlistBreakdown('b', [card])).toBe('')
    expect(shortlistBreakdown('a', undefined)).toBe('')
  })
})

describe('перцентиль в категории', () => {
  it('читает строку сервера', () => {
    expect(categoryBeats(['x', 'Выше среднего по категории Backend × middle: лучше 72 %'])).toBe(72)
    expect(categoryBeats(['ничего'])).toBeNull()
  })
})
