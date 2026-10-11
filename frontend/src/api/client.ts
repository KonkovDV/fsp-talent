import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { EXAMPLE_EVENT, exampleFixture, serverUnreachable } from '../demoFallback'
import { isTokenExpired, useAuthStore } from '../store/authStore'

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
  withCredentials: true,
})

function exampleResponse(config: InternalAxiosRequestConfig, data: unknown): AxiosResponse {
  return { data, status: 200, statusText: 'OK', headers: {}, config }
}

function exampleRejected(config: InternalAxiosRequestConfig): Promise<never> {
  return Promise.reject(new AxiosError(
    'example',
    AxiosError.ERR_BAD_REQUEST,
    config,
    null,
    { status: 409, statusText: 'Conflict', headers: {}, config, data: { error: { code: 'conflict', message: 'Это пример без сервера: действие не выполняется.' } } },
  ))
}

api.interceptors.request.use((config) => {
  if (useAuthStore.getState().example) {
    const method = (config.method ?? 'get').toLowerCase()
    if (method === 'get') {
      const data = exampleFixture(config.url)
      if (data !== undefined) config.adapter = () => Promise.resolve(exampleResponse(config, data))
    } else {
      config.adapter = () => exampleRejected(config)
    }
    return config
  }
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }
  return config
})

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const prefix = `${name}=`
  const found = document.cookie.split('; ').find(part => part.startsWith(prefix))
  return found ? decodeURIComponent(found.slice(prefix.length)) : undefined
}

function csrfHeader(): Record<string, string> {
  const token = readCookie('fsp_csrf')
  return token ? { 'X-CSRF-Token': token } : {}
}

let inflight: Promise<string | null> | null = null
let renewTimer: ReturnType<typeof setTimeout> | undefined

function tokenExpiry(token: string): number | null {
  try {
    const exp = JSON.parse(atob(token.split('.')[1]))['exp']
    return typeof exp === 'number' ? exp : null
  } catch {
    return null
  }
}

/** One refresh for every caller and every tab. Parallel 401s share it; a failure logs out once. */
export function renewAccess(): Promise<string | null> {
  if (!inflight) {
    const run = async () => {
      const before = useAuthStore.getState().token
      await useAuthStore.persist.rehydrate()
      const now = useAuthStore.getState().token
      if (now && now !== before && !isTokenExpired(now)) return now
      const response = await api.post('/auth/refresh', {}, { headers: csrfHeader() })
      const token = response.data?.access_token as string | undefined
      const role = useAuthStore.getState().userRole
      if (token && role) {
        useAuthStore.getState().setAuth(token, role)
        return token
      }
      useAuthStore.getState().logout()
      return null
    }
    const started: Promise<string | null> = typeof navigator !== 'undefined' && 'locks' in navigator
      ? navigator.locks.request('fsp-refresh', () => run() as unknown as string | null) as Promise<string | null>
      : run()
    inflight = started
      .catch(() => {
        useAuthStore.getState().logout()
        return null
      })
      .finally(() => { setTimeout(() => { inflight = null }, 0) })
  }
  return inflight
}

function armRenew(token: string | null) {
  if (renewTimer) clearTimeout(renewTimer)
  const exp = token ? tokenExpiry(token) : null
  if (!exp) return
  const wait = exp * 1000 - 60_000 - Date.now()
  const spread = Math.floor(Math.random() * 15_000)
  renewTimer = setTimeout(() => { void renewAccess() }, Math.max(0, wait - spread))
}

/** Refresh shortly before the access token expires, and when the jury comes back to the tab. */
export function installSessionRenew() {
  armRenew(useAuthStore.getState().token)
  useAuthStore.subscribe((state, previous) => {
    if (state.token !== previous.token) armRenew(state.token)
  })
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return
    const token = useAuthStore.getState().token
    const exp = token ? tokenExpiry(token) : null
    if (exp !== null && exp * 1000 - Date.now() < 120_000) void renewAccess()
  })
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const url = String(error.config?.url ?? '')
    const config = error.config as ({ _retried?: boolean } & NonNullable<typeof error.config>) | undefined
    if (error.response?.status === 429) {
      const header = Number(error.response.headers?.['retry-after'])
      const seconds = Number.isFinite(header) && header > 0 ? header : 60
      window.dispatchEvent(new CustomEvent('fsp-rate-limit', { detail: seconds }))
    }
    // A failed login is also 401. Reloading /login would wipe the error on the form.
    const method = String(error.config?.method ?? 'get').toLowerCase()
    const sample = exampleFixture(url)
    if (method === 'get' && sample !== undefined && serverUnreachable(error) && !useAuthStore.getState().example) {
      window.dispatchEvent(new CustomEvent(EXAMPLE_EVENT))
      return exampleResponse(config ?? error.config, sample)
    }
    if (error.response?.status === 401 && config && !url.includes('/auth/') && !config._retried && !useAuthStore.getState().example) {
      config._retried = true
      const token = await renewAccess()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
        return api(config)
      }
      if (window.location.pathname !== '/login') window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export async function signOut() {
  try { await api.post('/auth/logout', {}, { headers: csrfHeader() }) } catch { /* the cookie may already be gone */ }
  useAuthStore.getState().logout()
}

export const askGuide = (question: string) =>
  api.post<{ answer: string; links: { label: string; to: string }[] }>('/guide/ask', { question })
export const askPublicGuide = (question: string) =>
  api.post<{ answer: string; links: { label: string; to: string }[] }>('/public/guide', { question })

export type Role = 'participant' | 'employer'
const form = (username: string, password: string) =>
  [new URLSearchParams({ username, password }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }] as const

export const publicDemo = () => api.get<{ demo_mode: boolean; mail_console: boolean }>('/public/demo')
export const publicJuryFree = () => api.get<{ email: string }>('/public/jury-free')
export const guestLogin = (role: Role, consents: string[]) =>
  api.post<{ access_token: string; role: Role; guest_until: string }>('/auth/guest', { role, consents })
export const registerParticipant = (data: {
  email: string; password: string; display_name?: string; is_adult: boolean; age_15_17?: boolean; birth_date?: string; consents: string[]
}) => api.post('/auth/participant/register', data)
export const registerEmployer = (data: object) => api.post('/auth/employer/register', data)
export const verifyEmail = (data: { email?: string; code?: string; token?: string; role?: Role }) =>
  api.post('/auth/verify-email', data)
export const resendVerification = (email: string, role: Role) =>
  api.post('/auth/resend-verification', { email, role })
export const forgotPassword = (email: string, role: Role) => api.post('/auth/password/forgot', { email, role })
export const resetPassword = (data: { email: string; role: Role; code: string; new_password: string }) =>
  api.post('/auth/password/reset', data)
export const changePassword = (current_password: string, new_password: string) =>
  api.post('/auth/password/change', { current_password, new_password })
export const downloadMyData = () => api.get('/auth/me/export', { responseType: 'blob' })
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
// FSP ID by OpenID Connect (code flow + PKCE): the password is typed only on the provider's page.
export const fspAuthorize = () => api.post('/candidates/me/fsp/authorize')
export const fspCallback = (code: string, state: string) => api.post('/candidates/me/fsp/callback', { code, state })
export const fspDemoLogin = (body: Record<string, string>) => api.post('/fsp-id-demo/login', body)

export const getMyProfile = () => api.get('/candidates/me')
export const myCareer = () => api.get<{ skill: string | null; gained: number; vacancies: number }>('/candidates/me/career')
export const myExclusions = () => api.get<{ industries: string[]; companies: { id: string; name: string }[] }>('/candidates/me/exclusions')
export const setExclusions = (industries: string[]) => api.put('/candidates/me/exclusions', { industries })
export const blockCompany = (offer_id: string) => api.post('/candidates/me/blocks', { offer_id })
export const unblockCompany = (employerId: string) => api.delete(`/candidates/me/blocks/${employerId}`)
export const getMySalaryMarket = () => api.get('/candidates/me/salary-market')
export const getMyGrowth = () => api.get('/candidates/me/growth')
export const updateMyProfile = (data: object) => api.put('/candidates/me/profile', data)
export const listNotifications = () => api.get('/notifications')
export const readNotification = (id: string) => api.post(`/notifications/${id}/read`)
export const readAllNotifications = () => api.post('/notifications/read-all')
export const deleteMyAccount = (confirm: string, password = '') =>
  api.delete('/candidates/me', { data: { confirm, password } })
export const getMyResults = () => api.get('/candidates/me/results')
export const importCertificate = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return api.post<{ skills: string[]; grade_unchanged: boolean }>('/candidates/me/certificate', body)
}
export const importProtocols = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return api.post<{ added: number; read: number; grade_unchanged: boolean }>('/candidates/me/protocols', body)
}
export const getMyOffers = () => api.get('/candidates/me/offers', { params: { limit: 50 } })
export const respondToOffer = (offerId: string, action: 'accept' | 'reject', reason?: string) =>
  api.post(`/candidates/me/offers/${offerId}/respond`, { action, reason: reason || null })
export const fileComplaint = (offerId: string, reason: string) =>
  api.post('/candidates/me/complaints', { offer_id: offerId, reason })
export const updateVisibility = (is_visible: boolean) =>
  api.patch('/candidates/me/visibility', { is_visible })

export const searchCandidates = (params: object) => api.get('/search/candidates', { params })
export const searchBank = () => api.get('/search/bank')
export const askGuardian = (guardian_email: string) =>
  api.post<{ ok: boolean; guardian_email: string; demo_link: string | null }>('/candidates/me/guardian', { guardian_email })
export const guardianConsent = (token: string) => api.post('/public/guardian-consent', { token })
export const parseQuery = (q: string) => api.post('/ai/parse-query', { q })
export const parseResume = (text: string) => api.post('/ai/parse-resume', { text })

export interface AiNotePoint { text: string; facts: string[] }
export interface AiNote {
  summary: string; strengths: AiNotePoint[]; risks: AiNotePoint[]; questions: AiNotePoint[]
  dropped: number; provider: string; model: string; generated_at: string; affects_score: false; cached: boolean
}
export const getAiNote = (needId: string, candidateId: string) =>
  api.get<AiNote>(`/needs/${needId}/candidates/${candidateId}/ai-note`)
export const createOffer = (data: object, idempotencyKey?: string) =>
  api.post('/offers/', data, idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined)
export const previewOffer = (candidate_id: string, salary_to_gross: number, salary_from_gross?: number, salary_basis?: 'gross' | 'net') =>
  api.post('/offers/preview', { candidate_id, salary_to_gross, salary_from_gross, salary_basis })
export const offerMarket = () => api.get('/offers/market')
export const getMyEmployerOffers = () => api.get('/offers/')
export const getOfferContacts = (id: string) => api.get(`/offers/${id}/contacts`)
export const withdrawOffer = (id: string) => api.post(`/offers/${id}/withdraw`)
export const advancePractice = (id: string, stage: string) => api.post(`/offers/${id}/practice`, { stage })
export const getSlots = (offerId: string) => api.get(`/offers/${offerId}/slots`)
export const proposeSlots = (offerId: string, slots: object[]) => api.post(`/offers/${offerId}/slots`, { slots })
export const chooseSlot = (offerId: string, slotId: string) => api.post(`/offers/${offerId}/slots/${slotId}/choose`)
export const getInterviewCode = (offerId: string) => api.get(`/offers/${offerId}/code`)
export const openInterviewCode = (offerId: string, body: { problem_id?: string | null; prompt: string }) =>
  api.post(`/offers/${offerId}/code`, body)
export const saveInterviewCode = (offerId: string, text: string, version: number) =>
  api.put(`/offers/${offerId}/code`, { text, version })
export const disputeInterviewCode = (offerId: string, text: string) =>
  api.post(`/offers/${offerId}/code/dispute`, { text })
export const setInterviewOutcome = (offerId: string, outcome: string) =>
  api.post(`/offers/${offerId}/interview/outcome`, { outcome })
export const downloadInterview = (offerId: string) =>
  api.get(`/offers/${offerId}/interview.ics`, { responseType: 'blob' })

export const getEmployerMe = () => api.get('/employer/me')
export const getReputation = () => api.get('/employer/reputation')
export const atsSandbox = () => api.post('/employer/ats-sandbox')
export const updateEmployerMe = (data: object) => api.patch('/employer/me', data)
export const saveHiringPractice = (body: {
  feedback: boolean; platform_interview: boolean; task_review: boolean; salary_written: boolean
}) => api.post('/employer/me/hiring-practice', body)
export const getMyVacancies = () => api.get('/vacancies/mine', { params: { limit: 50 } })
export const updateVacancy = (id: string, data: object) => api.put(`/vacancies/${id}`, data)
export const updateApplicationStatus = (id: string, status: string) =>
  api.patch(`/vacancies/applications/${id}/status`, { status })
export const uploadResumePdf = (file: File) => {
  const body = new FormData()
  body.append('file', file)
  return api.post('/candidates/me/resume', body)
}
export const downloadMyProfilePdf = () => api.get('/candidates/me/profile.pdf', { responseType: 'blob' })
export const createVacancy = (data: object) => api.post('/vacancies/', data)
export const needExam = (id: string) => api.get(`/needs/${id}/exam`)
export const previewVacancyExam = (data: object) => api.post('/vacancies/exam', data)
export const previewPublicExam = (data: { description: string; role?: string; grade?: string }) =>
  api.post('/public/vacancy-preview', data)
export const closeVacancy = (id: string) => api.post(`/vacancies/${id}/close`)
export const vacanciesForMe = () => api.get('/vacancies/for-me')
export const applyToVacancy = (id: string) => api.post(`/vacancies/${id}/apply`)
export const vacancyApplications = () => api.get('/vacancies/applications', { params: { limit: 50 } })
export const applicationContacts = (id: string) => api.get(`/vacancies/applications/${id}/contacts`)

export const assessmentBlueprint = () => api.get('/assessment/blueprint')
export const startAssessment = (data: { target_grade: string; specialization?: string | null; code_language?: string; vacancy_id?: string | null; mode?: 'grade' | 'express' }, idempotencyKey?: string) =>
  api.post('/assessment/start', data, idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined)
export const activeAssessment = () => api.get('/assessment/active')
export const saveAssessmentDraft = (sessionId: string, body: {
  item_token: string; version: number; answer_index?: number | null; answer_text?: string | null
}) => api.put(`/assessment/${sessionId}/draft`, body)
export const answerAssessment = (sessionId: string, item_token: string,
  answer: { answer_index: number } | { answer_text: string }) =>
  api.post(`/assessment/${sessionId}/answer`, { item_token, ...answer }, {
    headers: { 'Idempotency-Key': `${sessionId}:${item_token}` },
  })
export const abandonAssessment = (sessionId: string) => api.post(`/assessment/${sessionId}/abandon`)
export const acceptLowerGrade = (sessionId: string) => api.post(`/assessment/${sessionId}/accept-lower`)
export const leaveAssessment = (sessionId: string) => api.post(`/assessment/${sessionId}/leave`)
export const noteAssessmentCopy = (sessionId: string) => api.post(`/assessment/${sessionId}/copy`)
export const disputeGrade = (sessionId: string) =>
  api.post<{ text: string }>(`/assessment/${sessionId}/dispute`)
export const reviewAssessment = (sessionId: string) => api.get(`/assessment/${sessionId}/review`)
export const assessmentCooldown = (specialization?: string) =>
  api.get('/assessment/cooldown', { params: specialization ? { specialization } : {} })
export const assessmentHistory = () => api.get('/assessment/history', { params: { limit: 100 } })
export const startPractice = (opts?: { vacancy_id?: string | null; topic?: string | null }) =>
  api.post('/assessment/practice/start', { vacancy_id: opts?.vacancy_id || null, topic: opts?.topic || null })
export const compareNeed = (needId: string, ids: string[]) =>
  api.get(`/needs/${needId}/compare`, { params: { ids: ids.join(',') } })
export const weeklyTask = () => api.get('/assessment/practice/weekly')
export const answerPractice = (id: string, body: { answer_index?: number; answer_text?: string }) =>
  api.post(`/assessment/practice/${id}/answer`, body)
export const myApplications = () => api.get('/vacancies/my-applications')
export const itemHealth = () => api.get('/public/assessment/items')
export const itemPsychometrics = (spec: string) => api.get('/public/assessment/psychometrics', { params: { spec } })
export const methodWeights = () => api.get<{
  fit: { key: string; label: string; weight: number }[]
  evidence: { key: string; label: string; weight: number }[]
  evidence_weight: number
  note: string
}>('/public/method/weights')

export const surveyOptions = () => api.get('/candidates/survey-options')
export const saveSurvey = (data: {
  specialization: string; industry: string; work_goal: string; declared_grade?: string | null; experience_years?: number | null
  salary_from_gross?: number | null; salary_to_gross?: number | null; salary_basis?: 'gross' | 'net'
  work_formats?: string[]; region?: string | null
}) => api.put('/candidates/me/survey', data)

export const getPublicProfile = (id: string) => api.get(`/public/candidates/${id}`)
export const getPublicCompany = (id: string) => api.get(`/public/companies/${id}`)
export const categoryRanking = (role: string, grade: string) =>
  api.get<{ total: number; items: { place: number; test: number }[] }>(`/public/categories/${role}/${grade}/ranking`)
export const telegramAchievements = (fspId: string) =>
  api.get('/public/telegram/achievements', { params: { fsp_id: fspId } })
export const telegramVacancies = () => api.get('/public/telegram/vacancies')
export const getLeaderboard = (discipline?: string) =>
  api.get('/public/leaderboard', { params: discipline ? { discipline } : {} })
export const getCredentials = (id: string) => api.get(`/public/credentials/${id}`)
export const verifyCredential = (credential: object) => api.post('/public/credentials/verify', credential)
export const issuerDid = () => api.get<{ id: string }>('/public/did.json')
export interface PassportGrade { specialization: string; grade: string; confirmedOn: string }
export interface PassportFsp { discipline: string; results: number; bestBucket: string; statuses: string[]; lastYear: number }
export interface PassportClaims { name?: string; grades: PassportGrade[]; testedSkills: string[]; fspResults: PassportFsp[] }
export interface PassportCredential { validFrom?: string; credentialSubject?: { achievement?: PassportClaims } }
export interface MyPassport { id: string; url: string; issued_at: string | null; credential: PassportCredential }
export interface PublicPassport { valid: boolean; signature: boolean; revoked: boolean; issued_at: string | null; credential: PassportCredential }
export const getMyPassport = () => api.get<MyPassport | null>('/candidates/me/passport')
export const issueMyPassport = () => api.post<MyPassport>('/candidates/me/passport')
export const revokeMyCredential = (id: string) => api.post(`/candidates/me/credentials/${id}/revoke`)
export const getPublicPassport = (id: string) => api.get<PublicPassport>(`/public/passport/${id}`)
export interface EvaluateRow { method: string; title: string; ndcg10: number; ndcg_ci: [number, number] | null; p10: number; map: number }
export interface EvaluateReport { pairs: number; needs: number; judged_needs: number; sha256: string; rows: EvaluateRow[] }
export const evaluatePairs = (text: string) =>
  api.post<EvaluateReport>('/public/evaluate', text, { headers: { 'Content-Type': 'text/plain' } })
export const credentialStatus = (id: string) => api.get(`/public/credentials/${id}/status`)
export const presentResult = (id: string) => api.post(`/candidates/me/results/${id}/presentation`)

export interface ResumeRow {
  id: string | null; specialization: string; label: string; grade: string | null
  stack?: string[]; summary?: string | null; grade_source?: string; primary?: boolean
}
export interface ResumesData { primary: ResumeRow | null; extras: ResumeRow[]; extra_max: number }
export interface ResumeBody { specialization: string; grade: string; stack: string[]; summary: string | null }
export const listResumes = () => api.get<ResumesData>('/candidates/me/resumes')
export const addResume = (body: ResumeBody) => api.post<ResumesData>('/candidates/me/resumes', body)
export const updateResume = (id: string, body: ResumeBody) => api.put<ResumesData>(`/candidates/me/resumes/${id}`, body)
export const deleteResume = (id: string) => api.delete<ResumesData>(`/candidates/me/resumes/${id}`)

export const listFavorites = () => api.get('/employer/favorites')
export const setFavoriteInterest = (id: string, interest: 'saved' | 'priority') =>
  api.put(`/employer/favorites/${id}`, { interest })
export const markCompanyInterest = (employerId: string, on: boolean) =>
  on ? api.post(`/candidates/me/interests/${employerId}`) : api.delete(`/candidates/me/interests/${employerId}`)
export const setFavorite = (id: string, on: boolean) =>
  on ? api.post(`/employer/favorites/${id}`) : api.delete(`/employer/favorites/${id}`)

export const listNeeds = () => api.get('/needs')
export const createNeed = (data: object) => api.post('/needs', data)
export const draftNeed = (text: string) => api.post('/needs/draft', { text })
export const draftNeedFromUrl = (url: string) => api.post('/needs/draft-url', { url })
export const updateNeed = (id: string, data: object) => api.put(`/needs/${id}`, data)
export const getNeed = (id: string) => api.get(`/needs/${id}`)
export const restoreNeed = (id: string, version: number) => api.post(`/needs/${id}/versions/${version}/restore`)
export const archiveNeed = (id: string) => api.delete(`/needs/${id}`)
export const needMatches = (id: string, showHidden = false) =>
  api.get(`/needs/${id}/matches`, { params: { limit: 50, show_hidden: showHidden } })
export const hideCandidate = (id: string, candidateId: string) => api.put(`/needs/${id}/hidden/${candidateId}`)
export const unhideCandidate = (id: string, candidateId: string) => api.delete(`/needs/${id}/hidden/${candidateId}`)
export const needShortlist = (id: string, status?: string) =>
  api.get(`/needs/${id}/shortlist`, { params: status ? { status } : {} })
export const setShortlist = (id: string, candidateId: string, status = 'shortlisted') =>
  api.put(`/needs/${id}/shortlist/${candidateId}`, { status })
export const removeShortlist = (id: string, candidateId: string) => api.delete(`/needs/${id}/shortlist/${candidateId}`)

// Sign-in by FSP ID: the Federation's single entry point. A new person accepts the consents before the account exists.
export const fspSignInAuthorize = () => api.post('/auth/fsp/authorize')
export const fspSignInCallback = (code: string, state: string) => api.post('/auth/fsp/callback', { code, state })
export const fspSignUp = (ticket: string, consents: string[]) => api.post('/auth/fsp/signup', { ticket, consents })

// Tasks written by employers: a reference answer is checked by the system, an open one by the employer.
export type TaskAnswerType = 'number' | 'choice' | 'open' | 'code' | 'regex'
export interface TaskSubmission {
  id: string; status: 'checked' | 'review' | 'reviewed'; status_label: string; passed: boolean | null
  comment: string | null; answer_text: string | null; answer_index: number | null
  submitted_at: string | null; reviewed_at: string | null
}
export interface CandidateTask {
  id: string; title: string; statement: string; answer_type: TaskAnswerType; options: { index: number; text: string }[]
  company: string | null; addressed: boolean; vacancy_id: string | null; deadline: string | null; created_at: string | null
  accepts_answers: boolean; submission: TaskSubmission | null; reference?: string | null
  languages?: CodeLanguage[]
}
export type CodeLanguage = 'python' | 'javascript'
export interface EmployerTask {
  id: string; title: string; statement: string; answer_type: TaskAnswerType; options: string[]; correct_index: number | null
  reference_number: string | null; visibility: 'public' | 'addressed'; specialization: string | null
  candidate_id: string | null; vacancy_id: string | null; deadline: string | null; is_open: boolean
  accepts_answers: boolean; created_at: string | null; lab_title?: string | null
  submissions: number; passed: number; awaiting_review: number
}
export type ReviewedSubmission = TaskSubmission & { candidate_id: string; candidate: string }
export const labProblems = () =>
  api.get<{ id: string; title: string; statement: string; languages: CodeLanguage[] }[]>('/tasks/lab')
export const createTask = (data: object) => api.post<EmployerTask>('/tasks/', data)
export const myTasks = () => api.get<EmployerTask[]>('/tasks/mine')
export const taskSubmissions = (id: string) =>
  api.get<{ task: EmployerTask; submissions: ReviewedSubmission[] }>(`/tasks/${id}/submissions`)
export const closeTask = (id: string) => api.post(`/tasks/${id}/close`)
export const reviewSubmission = (id: string, passed: boolean, comment: string) =>
  api.post(`/tasks/submissions/${id}/review`, { passed, comment: comment || null })
export const tasksForMe = () => api.get<CandidateTask[]>('/tasks/for-me')
export const answerTask = (id: string, body: { answer_text?: string; answer_index?: number; language?: CodeLanguage }) =>
  api.post<CandidateTask>(`/tasks/${id}/answer`, body)

// Contacts closed for one company, and messages after an accepted invitation.
export const revokeContacts = (offerId: string) => api.post(`/candidates/me/offers/${offerId}/revoke-contacts`)
export interface ThreadMessage { id: string; mine: boolean; author: 'participant' | 'employer'; body: string; created_at: string; read: boolean }
export const listMessages = (offerId: string) => api.get<{ can_post: boolean; messages: ThreadMessage[] }>(`/offers/${offerId}/messages`)
export const postMessage = (offerId: string, body: string) => api.post<ThreadMessage>(`/offers/${offerId}/messages`, { body })

/** Form limits served by the backend (audit-3 P1-2), so the salary floor lives in one place. */
export const getLimits = () => api.get<{ min_monthly_gross: number }>('/public/limits').then(r => r.data)
