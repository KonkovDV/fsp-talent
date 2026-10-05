import axios from 'axios'
import { useAuthStore } from '../store/authStore'

type ErrorPayload = { error?: { code?: string; message?: string; details?: unknown }; detail?: unknown }

function payloadOf(error: unknown): ErrorPayload | undefined {
  return (error as { response?: { data?: ErrorPayload } })?.response?.data
}

/** Stable machine code from the API error envelope (docs/API_ERRORS.md). */
export function apiErrorCode(error: unknown): string | undefined {
  return payloadOf(error)?.error?.code
}

export function apiErrorDetails<T = Record<string, unknown>>(error: unknown): T | undefined {
  return payloadOf(error)?.error?.details as T | undefined
}

export function apiError(error: unknown, fallback = 'Ошибка'): string {
  const data = payloadOf(error)
  const detail = data?.detail
  if (Array.isArray(detail)) {
    const text = detail.map((item) => (typeof item === 'string' ? item : (item as { msg?: string }).msg ?? '')).filter(Boolean).join('; ')
    return text || fallback
  }
  if (data?.error?.message) return data.error.message
  if (typeof detail === 'string') return detail
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
    const url = String(error.config?.url ?? '')
    // A failed login is also 401. Reloading /login would wipe the error on the form.
    if (error.response?.status === 401 && !url.includes('/auth/')) {
      useAuthStore.getState().logout()
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export type Role = 'participant' | 'employer'
const form = (username: string, password: string) =>
  [new URLSearchParams({ username, password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }] as const

export const registerParticipant = (data: {
  email: string; password: string; display_name?: string; is_adult: boolean; consents: string[]
}) => api.post('/auth/participant/register', data)
export const registerEmployer = (data: object) => api.post('/auth/employer/register', data)
export const verifyEmail = (data: { email?: string; code?: string; token?: string; role?: Role }) =>
  api.post('/auth/verify-email', data)
export const resendVerification = (email: string, role: Role) =>
  api.post('/auth/resend-verification', { email, role })
export const forgotPassword = (email: string, role: Role) => api.post('/auth/password/forgot', { email, role })
export const resetPassword = (data: { email: string; role: Role; code: string; new_password: string }) =>
  api.post('/auth/password/reset', data)
export const loginParticipant = (email: string, password: string) =>
  api.post('/auth/participant/token', ...form(email, password))
export const loginEmployer = (email: string, password: string) =>
  api.post('/auth/employer/token', ...form(email, password))

export interface LegalDoc { kind: string; version: string; title: string; required: boolean; roles: string[]; sha256: string }
export const legalDocuments = (role?: Role) =>
  api.get<LegalDoc[]>('/legal/documents', { params: role ? { role } : {} })
export const legalDocument = (kind: string) => api.get<LegalDoc & { body_md: string }>(`/legal/documents/${kind}`)
export const myConsents = () => api.get('/me/consents')
export const giveConsent = (kind: string) => api.post('/me/consents', { kind })
export const withdrawConsent = (kind: string) => api.delete(`/me/consents/${kind}`)
export const linkFsp = (fsp_id: string, fsp_secret: string) => api.post('/candidates/me/fsp', { fsp_id, fsp_secret })

export const getMyProfile = () => api.get('/candidates/me')
export const updateMyProfile = (data: object) => api.put('/candidates/me/profile', data)
export const listNotifications = () => api.get('/notifications')
export const readNotification = (id: string) => api.post(`/notifications/${id}/read`)
export const readAllNotifications = () => api.post('/notifications/read-all')
export const deleteMyAccount = (confirm: string) => api.delete('/candidates/me', { data: { confirm } })
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

export const getMyVacancies = () => api.get('/vacancies/mine')
export const createVacancy = (data: object) => api.post('/vacancies/', data)
export const previewVacancyExam = (data: object) => api.post('/vacancies/exam', data)
export const closeVacancy = (id: string) => api.post(`/vacancies/${id}/close`)
export const vacanciesForMe = () => api.get('/vacancies/for-me')
export const applyToVacancy = (id: string) => api.post(`/vacancies/${id}/apply`)
export const vacancyApplications = () => api.get('/vacancies/applications')
export const applicationContacts = (id: string) => api.get(`/vacancies/applications/${id}/contacts`)

export const assessmentBlueprint = () => api.get('/assessment/blueprint')
export const startAssessment = (data: { target_grade: string; specialization?: string | null; code_language?: string; vacancy_id?: string | null }) =>
  api.post('/assessment/start', data)
export const activeAssessment = () => api.get('/assessment/active')
export const answerAssessment = (sessionId: string, item_token: string, answer_index: number) =>
  api.post(`/assessment/${sessionId}/answer`, { item_token, answer_index })
export const abandonAssessment = (sessionId: string) => api.post(`/assessment/${sessionId}/abandon`)
export const reviewAssessment = (sessionId: string) => api.get(`/assessment/${sessionId}/review`)
export const assessmentCooldown = (specialization?: string) =>
  api.get('/assessment/cooldown', { params: specialization ? { specialization } : {} })
export const assessmentHistory = () => api.get('/assessment/history')
export const startPractice = (opts?: { vacancy_id?: string | null; topic?: string | null }) =>
  api.post('/assessment/practice/start', { vacancy_id: opts?.vacancy_id || null, topic: opts?.topic || null })
export const compareNeed = (needId: string, ids: string[]) =>
  api.get(`/needs/${needId}/compare`, { params: { ids: ids.join(',') } })
export const answerPractice = (id: string, answer_index: number) =>
  api.post(`/assessment/practice/${id}/answer`, { answer_index })
export const myApplications = () => api.get('/vacancies/my-applications')
export const itemHealth = () => api.get('/public/assessment/items')

export const surveyOptions = () => api.get('/candidates/survey-options')
export const saveSurvey = (data: {
  specialization: string; industry: string; work_goal: string; declared_grade?: string | null; experience_years?: number | null
}) => api.put('/candidates/me/survey', data)

export const getPublicProfile = (id: string) => api.get(`/public/candidates/${id}`)
export const getLeaderboard = (discipline?: string) =>
  api.get('/public/leaderboard', { params: discipline ? { discipline } : {} })
export const getCredentials = (id: string) => api.get(`/public/credentials/${id}`)
export const verifyCredential = (credential: object) => api.post('/public/credentials/verify', credential)

export const listNeeds = () => api.get('/needs')
export const createNeed = (data: object) => api.post('/needs', data)
export const updateNeed = (id: string, data: object) => api.put(`/needs/${id}`, data)
export const archiveNeed = (id: string) => api.delete(`/needs/${id}`)
export const needMatches = (id: string) => api.get(`/needs/${id}/matches`, { params: { limit: 20 } })
export const needShortlist = (id: string) => api.get(`/needs/${id}/shortlist`)
export const setShortlist = (id: string, candidateId: string, status = 'shortlisted') =>
  api.put(`/needs/${id}/shortlist/${candidateId}`, { status })
export const removeShortlist = (id: string, candidateId: string) => api.delete(`/needs/${id}/shortlist/${candidateId}`)
