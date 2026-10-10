import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Role = 'participant' | 'employer'

interface AuthFields {
  token: string | null
  userRole: Role | null
  userId: string | null
  needsRenew: boolean
  /** Demo guest account: the moment its sessions close. */
  guestUntil: string | null
  /** Read-only cabinet of sample cards, used when the server does not answer. */
  example: boolean
}

interface AuthState extends AuthFields {
  /** A renewal passes no guestUntil and keeps the one of the same account. */
  setAuth: (token: string, role: Role, guestUntil?: string | null) => void
  enterExample: (role: Role) => void
  logout: () => void
}

const SIGNED_OUT: AuthFields = { token: null, userRole: null, userId: null, needsRenew: false, guestUntil: null, example: false }

function parseJwtPayload(token: string): Record<string, unknown> {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return {}
  }
}

// A token saved in localStorage may be long expired by the next visit. Treat it as signed out
// instead of sending it and bouncing off a 401. 30 s of slack for clock skew.
export function isTokenExpired(token: string | null, nowSeconds = Date.now() / 1000): boolean {
  if (!token) return true
  const exp = parseJwtPayload(token)['exp']
  if (typeof exp !== 'number') return true
  return nowSeconds > exp - 30
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...SIGNED_OUT,
      setAuth: (token, role, guestUntil) => {
        const payload = parseJwtPayload(token)
        const userId = String(payload['sub'] ?? '')
        const kept = get().userId === userId ? get().guestUntil : null
        set({ token, userRole: role, userId, needsRenew: false, example: false, guestUntil: guestUntil !== undefined ? guestUntil : kept })
      },
      enterExample: (role) => set({ ...SIGNED_OUT, example: true, userRole: role, userId: 'example' }),
      logout: () => set(SIGNED_OUT),
    }),
    {
      name: 'fsp-auth',
      // Runs while the store is being created, so it must not touch useAuthStore itself.
      // The refresh token is an HttpOnly cookie, so a copy in this store is dropped.
      merge: (persisted, current) => {
        const saved = (persisted ?? {}) as Partial<AuthFields> & { refreshToken?: string | null }
        if (saved.example && (saved.userRole === 'participant' || saved.userRole === 'employer')) {
          return { ...current, ...SIGNED_OUT, example: true, userRole: saved.userRole, userId: 'example' }
        }
        if (isTokenExpired(saved.token ?? null)) {
          // The access token died. The refresh cookie may still be alive, so keep the role and renew once.
          if (!saved.userRole) return { ...current, ...SIGNED_OUT }
          return {
            ...current,
            token: null,
            userRole: saved.userRole,
            userId: saved.userId ?? null,
            needsRenew: true,
            guestUntil: saved.guestUntil ?? null,
            example: false,
          }
        }
        return {
          ...current,
          token: saved.token ?? null,
          userRole: saved.userRole ?? null,
          userId: saved.userId ?? null,
          needsRenew: false,
          guestUntil: saved.guestUntil ?? null,
          example: false,
        }
      },
      // merge only fixes the in-memory state. Writing it back through the store's own action also
      // wipes the stale tokens from localStorage.
      onRehydrateStorage: () => (state) => {
        if (state?.example) return
        if (state && !state.token && !state.needsRenew) state.logout()
      },
    },
  ),
)
