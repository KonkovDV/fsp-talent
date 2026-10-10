import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import PassportCard from '../PassportCard'
import PassportPage from '../../pages/PassportPage'

const { getMyPassport, issueMyPassport, revokeMyCredential, getPublicPassport } = vi.hoisted(() => ({
  getMyPassport: vi.fn(), issueMyPassport: vi.fn(), revokeMyCredential: vi.fn(), getPublicPassport: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, getMyPassport, issueMyPassport, revokeMyCredential, getPublicPassport }
})

const claims = {
  grades: [{ specialization: 'Бэкенд', grade: 'middle', confirmedOn: '2026-10-10' }],
  testedSkills: ['Python', 'SQL'],
  fspResults: [{ discipline: 'Продуктовое программирование', results: 2, bestBucket: 'топ-5%', statuses: ['всероссийское'], lastYear: 2025 }],
}
const credential = { credentialSubject: { achievement: claims } }
const mine = { id: 'p1', url: 'https://talent.example/passport/p1', issued_at: '2026-10-10T09:00:00Z', credential }

function wrap(ui: React.ReactNode, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/" element={ui} /><Route path="/passport/:id" element={ui} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('паспорт навыков', () => {
  it('кандидат выпускает паспорт, видит ссылку и QR, отзывает', async () => {
    getMyPassport.mockResolvedValue({ data: null })
    issueMyPassport.mockResolvedValue({ data: mine })
    revokeMyCredential.mockResolvedValue({ data: {} })
    wrap(<PassportCard />)
    await userEvent.click(await screen.findByTestId('passport-issue'))
    expect(await screen.findByTestId('passport-link')).toHaveAttribute('href', mine.url)
    expect(screen.getByTestId('qr-code').querySelector('path')?.getAttribute('d')).toMatch(/^M\d/)
    await userEvent.click(screen.getByRole('button', { name: 'Отозвать' }))
    await waitFor(() => expect(revokeMyCredential).toHaveBeenCalledWith('p1'))
    expect(await screen.findByTestId('passport-issue')).toBeInTheDocument()
  })

  it('публичная страница показывает проверку подписи и подтверждённое', async () => {
    getPublicPassport.mockResolvedValue({ data: { valid: true, signature: true, revoked: false, issued_at: mine.issued_at, credential } })
    wrap(<PassportPage />, '/passport/p1')
    expect(await screen.findByTestId('passport-verdict')).toHaveTextContent('Подпись платформы верна')
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText(/топ-5%/)).toBeInTheDocument()
    expect(getPublicPassport).toHaveBeenCalledWith('p1')
  })

  it('отозванный паспорт не показывает содержимое', async () => {
    getPublicPassport.mockResolvedValue({ data: { valid: false, signature: true, revoked: true, issued_at: mine.issued_at, credential } })
    wrap(<PassportPage />, '/passport/p1')
    expect(await screen.findByTestId('passport-verdict')).toHaveTextContent('отозван')
    expect(screen.queryByText('Python')).not.toBeInTheDocument()
  })
})
