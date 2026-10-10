import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Profile from '../candidate/Profile'

const updateMyProfile = vi.fn()

vi.mock('../../api/client', () => ({
  getMyProfile: () => Promise.resolve({
    data: {
      display_name: 'Аня', email: 'anya@demo.talent', is_visible: true, discoverable: true,
      job_search: 'open', show_city: true, public_profile: false, profile_version: 3,
      skills: [], specialization: 'backend', industry: 'fintech',
    },
  }),
  updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
  updateVisibility: vi.fn(),
  myExclusions: () => Promise.resolve({ data: { industries: [], companies: [] } }),
  surveyOptions: () => Promise.resolve({ data: { industries: { fintech: 'Финтех' } } }),
  setExclusions: vi.fn(),
  giveConsent: vi.fn(),
  downloadMyProfilePdf: vi.fn(),
  parseResume: vi.fn(),
  uploadResumePdf: vi.fn(),
}))

function renderProfile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><Profile /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('видимость города', () => {
  beforeEach(() => updateMyProfile.mockReset())

  it('показывает три шага разбора резюме', async () => {
    renderProfile()
    expect(await screen.findByText(/Вставьте текст или загрузите PDF/)).toBeInTheDocument()
    expect(screen.getByText(/дословной цитатой/)).toBeInTheDocument()
    expect(screen.getByText(/Подставьте нужные строки/)).toBeInTheDocument()
  })

  it('скрывает город и передаёт версию профиля', async () => {
    updateMyProfile.mockResolvedValue({ data: { ok: true } })
    renderProfile()
    await userEvent.click(await screen.findByRole('button', { name: 'Город виден работодателям' }))
    expect(updateMyProfile).toHaveBeenCalledWith({ show_city: false, expected_version: 3 })
  })
})
