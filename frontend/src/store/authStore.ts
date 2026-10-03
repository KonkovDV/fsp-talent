import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  token: string | null
  refreshToken: string | null
  userRole: 'participant' | 'employer' | null
  userId: string | null
  setAuth: (token: string, refreshToken: string, role: 'participant' | 'employer') => void
  logout: () => void
}

function parseJwtPayload(token: string): Record<string, string> {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return {}
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      userRole: null,
      userId: null,
      setAuth: (token, refreshToken, role) => {
        const payload = parseJwtPayload(token)
        set({ token, refreshToken, userRole: role, userId: payload.sub })
      },
      logout: () => set({ token: null, refreshToken: null, userRole: null, userId: null }),
    }),
    { name: 'fsp-auth' }
  )
)
