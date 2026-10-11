import { describe, expect, it } from 'vitest'
import { contactOk } from '../contact'

describe('способ связи в приглашении', () => {
  it('пропускает почту, @ник и телефон E.164', () => {
    for (const v of ['hr@sibcode.demo', '@sibcode_hr', '+7 (999) 123-45-67', 'hr@sibcode.demo, @sibcode_hr']) expect(contactOk(v)).toBe(true)
  })
  it('не пропускает ссылки без http и свободный текст', () => {
    for (const v of ['t.me/x', 'evil.ru/login', 'bit.ly/abc', 'https://evil.example', 'почта', '@abc', '']) expect(contactOk(v)).toBe(false)
  })
})
