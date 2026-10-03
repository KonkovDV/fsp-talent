import axios from 'axios'
import { useAuthStore } from '../store/authStore'

export function apiError(error: unknown, fallback = 'Ошибка'): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const text = detail.map((item) => (typeof item === 'string' ? item : (item as { msg?: string }).msg ?? '')).filter(Boolean).join('; ')
    return text || fallback
  }
  return fallback
}

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const registerParticipant = (data: { fsp_id: string; fsp_secret: string }) =>
  api.post('/auth/participant/register', data)
export const loginParticipant = (fsp_id: string, password: string) =>
  api.post('/auth/participant/token', new URLSearchParams({ username: fsp_id, password }),
           { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
export const registerEmployer = (data: object) => api.post('/auth/employer/register', data)
export const loginEmployer = (email: string, password: string) =>
  api.post('/auth/employer/token', new URLSearchParams({ username: email, password }),
           { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })

export const getMyProfile = () => api.get('/candidates/me')
export const updateMyProfile = (data: object) => api.put('/candidates/me/profile', data)
export const getMyResults = () => api.get('/candidates/me/results')
export const getMyOffers = () => api.get('/candidates/me/offers')
export const respondToOffer = (offerId: string, action: 'accept' | 'reject') =>
  api.post(`/candidates/me/offers/${offerId}/respond`, { action })
export const updateVisibility = (is_visible: boolean) =>
  api.patch('/candidates/me/visibility', { is_visible })

export const searchCandidates = (params: object) => api.get('/search/candidates', { params })
export const parseQuery = (q: string) => api.post('/ai/parse-query', { q })
export const parseResume = (text: string) => api.post('/ai/parse-resume', { text })

export const createOffer = (data: object) => api.post('/offers/', data)
export const getMyEmployerOffers = () => api.get('/offers/')
export const getOfferContacts = (id: string) => api.get(`/offers/${id}/contacts`)
export const withdrawOffer = (id: string) => api.post(`/offers/${id}/withdraw`)

export const getPublicProfile = (id: string) => api.get(`/public/candidates/${id}`)
export const getLeaderboard = (discipline?: string) =>
  api.get('/public/leaderboard', { params: discipline ? { discipline } : {} })
export const getCredentials = (id: string) => api.get(`/public/credentials/${id}`)
export const verifyCredential = (credential: object) => api.post('/public/credentials/verify', credential)
