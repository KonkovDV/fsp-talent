import { describe, expect, it } from 'vitest'
import { passwordRule } from '../passwordRule'

const accepts = (password: string) => passwordRule.safeParse(password).success

describe('passwordRule', () => {
  it('accepts 72 bytes of Latin letters and rejects 73', () => {
    expect(accepts('a'.repeat(72))).toBe(true)
    expect(accepts('a'.repeat(73))).toBe(false)
  })

  it('counts Cyrillic in bytes: 36 letters are 72 bytes, 37 are not', () => {
    expect(accepts('я'.repeat(36))).toBe(true)
    expect(accepts('я'.repeat(37))).toBe(false)
  })

  it('still needs at least 8 characters', () => {
    expect(accepts('1234567')).toBe(false)
    expect(accepts('12345678')).toBe(true)
  })

  it('counts an emoji as one character, as the server does', () => {
    expect(accepts('😀'.repeat(4))).toBe(false) // 4 code points: the server refuses it
    expect(accepts('😀'.repeat(8))).toBe(true)
  })

  it('counts an emoji as four bytes', () => {
    expect(accepts('😀'.repeat(18))).toBe(true) // 72 bytes
    expect(accepts('😀'.repeat(19))).toBe(false) // 76 bytes
  })
})
