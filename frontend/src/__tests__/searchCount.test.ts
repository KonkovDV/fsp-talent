import { describe, expect, it } from 'vitest'
import { searchCount } from '../searchCount'

describe('searchCount', () => {
  it('without a category the headline is the total', () => {
    expect(searchCount(16, null)).toEqual({ main: 16, related: 0 })
    expect(searchCount(16, undefined)).toEqual({ main: 16, related: 0 })
  })
  it('with role and grade the neighbours are counted apart, so the headline does not grow', () => {
    expect(searchCount(23, 9)).toEqual({ main: 9, related: 14 })
    expect(searchCount(5, 5)).toEqual({ main: 5, related: 0 })
    expect(searchCount(4, 0)).toEqual({ main: 0, related: 4 })
  })
  it('never reports more in the category than in the list', () => {
    expect(searchCount(3, 7)).toEqual({ main: 3, related: 0 })
  })
})
