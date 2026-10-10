import { describe, expect, it } from 'vitest'
import { grossForNet, netMonthly } from './money'

describe('НДФЛ', () => {
  it('200 000 до НДФЛ — 174 000 на руки, на границе шкалы', () => {
    expect(netMonthly(200_000)).toBe(174_000)
    expect(netMonthly(300_000)).toBe(259_000)
  })
  it('обратный перевод не уходит дальше 100 ₽', () => {
    for (const net of [100_000, 174_000, 250_000]) {
      const back = netMonthly(grossForNet(net))
      expect(back - net).toBeGreaterThanOrEqual(0)
      expect(back - net).toBeLessThanOrEqual(100)
    }
  })
})
