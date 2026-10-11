import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CandidateVacancies from '../candidate/Vacancies'

const { vacanciesForMe, getMyProfile } = vi.hoisted(() => ({ vacanciesForMe: vi.fn(), getMyProfile: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, vacanciesForMe, getMyProfile, myApplications: vi.fn(() => Promise.resolve({ data: [] })) }
})

const card = {
  id: 'v1', title: 'Backend-разработчик', description: '', role: 'backend', grade: 'senior', company: 'СибКод',
  skills: [], salary_from: 150000, salary_to: 200000, work_format: 'remote', why: [], matched_skills: [],
  missing_skills: [], coverage: 0, applied: false, can_apply: true,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><CandidateVacancies /></MemoryRouter></QueryClientProvider>)
}

describe('вакансии кандидата', () => {
  beforeEach(() => { getMyProfile.mockResolvedValue({ data: { birth_date: '1998-05-01' } }) })
  it('без теста показывает все открытые вакансии и зовёт пройти тест', async () => {
    vacanciesForMe.mockResolvedValue({ data: [{ ...card, match: 'not_assessed', needs_test: true, can_apply: false }] })
    renderPage()
    expect(await screen.findByText(/Пройдите тест — вакансии отсортируются по совпадению/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сначала тест на грейд' })).toBeDisabled()
    expect(screen.getByText('Backend-разработчик')).toBeInTheDocument()
  })
  it('с грейдом подсказки нет', async () => {
    vacanciesForMe.mockResolvedValue({ data: [{ ...card, match: 'matched' }] })
    renderPage()
    expect(await screen.findByText('Backend-разработчик')).toBeInTheDocument()
    expect(screen.queryByText(/Пройдите тест/)).not.toBeInTheDocument()
  })
  it('без даты рождения объясняет, почему вакансий мало, и ведёт в профиль', async () => {
    getMyProfile.mockResolvedValue({ data: { birth_date: null } })
    vacanciesForMe.mockResolvedValue({ data: [] })
    renderPage()
    const hint = await screen.findByTestId('vacancies-birth-date')
    expect(hint).toHaveTextContent(/дату рождения/)
    expect(screen.getByRole('link', { name: 'профиле' })).toHaveAttribute('href', '/candidate/profile')
  })
  it('с датой рождения подсказки о дате нет', async () => {
    vacanciesForMe.mockResolvedValue({ data: [{ ...card, match: 'matched' }] })
    renderPage()
    expect(await screen.findByText('Backend-разработчик')).toBeInTheDocument()
    expect(screen.queryByTestId('vacancies-birth-date')).not.toBeInTheDocument()
  })
})
