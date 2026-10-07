import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Role = 'participant' | 'employer'

interface AuthFields {
  token: string | null
  userRole: Role | null
  userId: string | null
}

interface AuthState extends AuthFields {
  setAuth: (token: string, role: Role) => void
  logout: () => void
}

const SIGNED_OUT: AuthFields = { token: null, userRole: null, userId: null }

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
    (set) => ({
      ...SIGNED_OUT,
      setAuth: (token, role) => {
        const payload = parseJwtPayload(token)
        set({ token, userRole: role, userId: String(payload['sub'] ?? '') })
      },
      logout: () => set(SIGNED_OUT),
    }),
    {
      name: 'fsp-auth',
      // Runs while the store is being created, so it must not touch useAuthStore itself.
      // The refresh token is an HttpOnly cookie, so a copy in this store is dropped.
      merge: (persisted, current) => {
        const saved = (persisted ?? {}) as Partial<AuthFields> & { refreshToken?: string | null }
        if (isTokenExpired(saved.token ?? null)) return { ...current, ...SIGNED_OUT }
        return {
          ...current,
          token: saved.token ?? null,
          userRole: saved.userRole ?? null,
          userId: saved.userId ?? null,
        }
      },
      // merge only fixes the in-memory state. Writing it back through the store's own action also
      // wipes the stale tokens from localStorage.
      onRehydrateStorage: () => (state) => {
        if (state && !state.token) state.logout()
      },
    },
  ),
)
