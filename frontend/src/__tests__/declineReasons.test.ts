import { describe, expect, it } from 'vitest'
import { declineReasons } from '../declineReasons'

describe('причины отказа', () => {
  it('считает только отказы и сортирует по частоте', () => {
    expect(declineReasons([
      { status: 'rejected', decline_reason: 'salary' },
      { status: 'rejected', decline_reason: 'salary' },
      { status: 'rejected', decline_reason: null },
      { status: 'accepted', decline_reason: 'stack' },
    ])).toEqual([['Зарплата', 2], ['Не указана', 1]])
  })
  it('пусто без отказов', () => {
    expect(declineReasons([{ status: 'pending' }])).toEqual([])
  })
})
