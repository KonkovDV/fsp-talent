/** A labeled example for the jury walkthrough when the server does not answer.

The figures are a teaching sample: no names, no contacts. Writes are refused.
A live 4xx or 5xx from the application is not replaced: only silence and a gateway error.
*/

const CARD = {
  region: 'Новосибирск',
  experience_years: 3,
  matched_skills: ['Python'],
  missing_skills: [],
  disciplines: [{ discipline: 'algorithmic', label: 'Алгоритмы', lcb: 0.62, confidence: 0.8, best_rank: 'I', events_count: 4, evidence: [] }],
  match: {
    score: 0.74,
    plus: ['Грейд подтверждён тестом'],
    minus: [],
    info: [],
    factors: [],
    reply: { p: 0.71, label: 'высокая' },
  },
}

const FIXTURES: Record<string, unknown> = {
  '/search/bank': {
    min_cell: 5,
    cells: [
      { role: 'backend', grade: 'middle', hidden: false, candidates: 12, tested: 8 },
      { role: 'frontend', grade: 'junior', hidden: false, candidates: 6, tested: 2 },
    ],
  },
  '/search/candidates': {
    total: 2,
    items: [
      { ...CARD, candidate_id: '00000000-0000-4000-8000-0000000000a1', role: 'backend', grade: 'middle', grade_source: 'assessed', stack: ['Python', 'PostgreSQL'], why: ['Грейд middle подтверждён тестом'] },
      { ...CARD, candidate_id: '00000000-0000-4000-8000-0000000000a2', role: 'frontend', grade: 'junior', grade_source: 'declared', stack: ['TypeScript'], why: ['Грейд заявлен'], match: { ...CARD.match, score: 0.41, reply: { p: 0.38, label: 'средняя' } } },
    ],
  },
  '/needs': [{ id: '00000000-0000-4000-8000-0000000000b1', title: 'Backend, мидл', version: 1, shortlist_count: 1 }],
  '/offers/': [],
  '/vacancies/applications': [],
  '/employer/favorites': { items: [], ids: [], hidden: 0, max: 200 },
  '/employer/me': {
    id: '00000000-0000-4000-8000-0000000000c1', company_name: 'Пример компании',
    email: 'example@example.invalid', inn: null, website: null, description: null, industry: null,
    subscription_tier: 'free', inn_checked: false,
  },
  '/candidates/me': {
    display_name: 'Пример', primary_role: 'backend', grade: 'middle', grade_source: 'assessed',
    survey_done: true, is_minor: false, is_visible: true, skills: [{ name: 'Python', trust_level: 'test_confirmed' }],
    discipline_scores: [],
  },
  '/candidates/me/offers': [],
  '/candidates/me/salary-market': { role: 'backend', grade: 'middle', cell: null, band: null },
  '/candidates/me/growth': { role: 'backend', grade: 'middle', next_grade: 'senior', people: null, gaps: [], next_market: null },
  '/assessment/practice/weekly': null,
  '/tasks/for-me': [],
}

export const EXAMPLE_EVENT = 'fsp-example'

export function examplePath(url: string | undefined): string {
  const path = (url ?? '').split('?')[0]
  return path.startsWith('/') ? path : `/${path}`
}

export function exampleFixture(url: string | undefined): unknown | undefined {
  const path = examplePath(url)
  return Object.prototype.hasOwnProperty.call(FIXTURES, path) ? FIXTURES[path] : undefined
}

/** The request never reached the application: no HTTP status, or a gateway in front of it. */
export function serverUnreachable(error: unknown): boolean {
  const code = (error as { code?: string })?.code
  if (code === 'ERR_CANCELED') return false
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === undefined) return true
  return status === 502 || status === 503 || status === 504
}
