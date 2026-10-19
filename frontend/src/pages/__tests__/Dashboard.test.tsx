import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Dashboard from '../candidate/Dashboard'

const override = vi.hoisted(() => ({
  profile: {} as Record<string, unknown>,
  career: null as Record<string, unknown> | null,
}))

vi.mock('../../api/client', () => ({
  apiError: () => 'ошибка',
  getMyOffers: () => Promise.resolve({ data: [] }),
  weeklyTask: () => Promise.resolve({ data: null }),
  tasksForMe: () => Promise.resolve({ data: [] }),
  getMySalaryMarket: () => Promise.resolve({ data: { role: 'backend', grade: 'middle', cell: null, band: null } }),
  getMyDemand: () => Promise.resolve({ data: { days: 90, companies: 4, invites: null } }),
  getMyGrowth: () => Promise.resolve({ data: { role: 'backend', grade: 'middle', next_grade: null, people: null, gaps: [], next_market: null } }),
  myCareer: () => Promise.resolve({
    data: override.career ?? { skill: 'PostgreSQL', gained: 2, vacancies: 4 },
  }),
  getMyProfile: () => Promise.resolve({
    data: {
      display_name: 'Аня Тестова', email_verified: true, survey_done: true, grade_source: 'declared',
      has_fsp: false, discoverable: true, is_minor: false, primary_role: 'backend', grade: 'middle',
      skills: [], discipline_scores: [],
      completeness: {
        percent: 63, done: 5, total: 8,
        items: [
          { code: 'email', label: 'Email подтверждён', done: true, href: null },
          { code: 'salary', label: 'Указаны ожидания по зарплате', done: false, href: '/candidate/profile' },
          { code: 'test', label: 'Грейд подтверждён тестом', done: false, href: '/candidate/assessment' },
        ],
      },
      ...override.profile,
    },
  }),
}))

describe('готовность профиля', () => {
  it('показывает процент и ссылки на недостающее', async () => {
    override.career = null
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByTestId('profile-completeness')).toHaveTextContent('63 %, 5 из 8')
    expect(screen.getByRole('link', { name: 'Указаны ожидания по зарплате' })).toHaveAttribute('href', '/candidate/profile')
    expect(screen.getByRole('link', { name: 'Грейд подтверждён тестом' })).toHaveAttribute('href', '/candidate/assessment')
    expect(screen.getByText(/ФСП ID не привязан/)).toBeInTheDocument()
    expect(await screen.findByText(/подойдут ещё 2 открытые вакансии\./)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Спрос на профиль' })).toBeInTheDocument()
    expect(screen.getByText(/4 компании открывали карточку за 90 дней/)).toBeInTheDocument()
  })
})

describe('первый экран кабинета', () => {
  function show() {
    override.career = null
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><Dashboard /></MemoryRouter></QueryClientProvider>)
  }

  it('здоровается полным именем, а не первым словом', async () => {
    override.profile = { display_name: 'Член жюри 1' }
    show()
    expect(await screen.findByRole('heading', { name: 'Здравствуйте, Член жюри 1' })).toBeInTheDocument()
  })

  it('без выбранного грейда не пишет крупно «джуниор»', async () => {
    override.profile = { grade: 'junior', grade_source: 'default', survey_done: false }
    show()
    expect(await screen.findByText(/Грейд не выбран\. До опроса карточка стоит в выдаче как/)).toBeInTheDocument()
    expect(screen.queryByText('джуниор', { exact: true })).not.toBeInTheDocument()
  })

  it('держит подсказку закрытой, пока компаний меньше трёх', async () => {
    override.career = { skill: null, gained: 0, vacancies: 4, open: false, need_companies: 3 }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Dashboard />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/появится после интереса 3 разных компаний/)).toBeInTheDocument()
    expect(screen.queryByText(/подойдут ещё/)).not.toBeInTheDocument()
  })
})
