import { describe, expect, it } from 'vitest'
import { localDay } from './localDay'

describe('местная дата', () => {
  it('берёт календарный день зрителя, а не сутки UTC', () => {
    expect(localDay(new Date(2026, 9, 10, 1, 30))).toBe('2026-10-10')
  })
})
