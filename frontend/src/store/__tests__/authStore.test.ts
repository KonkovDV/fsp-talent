import { beforeEach, describe, expect, it } from 'vitest'
import { isTokenExpired, useAuthStore } from '../authStore'

function jwt(exp: number) {
  return `h.${btoa(JSON.stringify({ exp, sub: 'person-1' }))}.s`
}

describe('срок токена', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.getState().logout()
  })

  it('считает токен просроченным за 30 секунд до exp', () => {
    const now = 1_700_000_000
    expect(isTokenExpired(jwt(now + 20), now)).toBe(true)
    expect(isTokenExpired(jwt(now + 40), now)).toBe(false)
    expect(isTokenExpired(null, now)).toBe(true)
  })

  it('после просрочки оставляет роль и просит тихое обновление', async () => {
    localStorage.setItem('fsp-auth', JSON.stringify({
      state: { token: jwt(Math.floor(Date.now() / 1000) - 120), userRole: 'participant', userId: 'person-1' },
      version: 0,
    }))
    await useAuthStore.persist.rehydrate()
    expect(useAuthStore.getState().needsRenew).toBe(true)
    expect(useAuthStore.getState().userRole).toBe('participant')
    expect(useAuthStore.getState().token).toBeNull()
  })
})
