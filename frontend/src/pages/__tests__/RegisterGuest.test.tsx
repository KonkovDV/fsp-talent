import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RegisterPage from '../RegisterPage'
import { useAuthStore } from '../../store/authStore'

const { publicDemo, guestLogin, legalDocuments } = vi.hoisted(() => ({
  publicDemo: vi.fn(), guestLogin: vi.fn(), legalDocuments: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, guestLogin, legalDocuments }
})

const docs = [
  { kind: 'terms', title: 'Пользовательское соглашение', required: true, version: '1', sha256: 'a'.repeat(64), roles: ['participant'] },
  { kind: 'pd_candidate', title: 'Согласие на обработку', required: true, version: '1', sha256: 'b'.repeat(64), roles: ['participant'] },
]
const token = `x.${btoa(JSON.stringify({ sub: 'g1', exp: 4102444800 }))}.y`

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><RegisterPage /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  useAuthStore.getState().logout()
  legalDocuments.mockResolvedValue({ data: docs })
})

describe('гостевой вход', () => {
  it('ждёт согласий и входит без почты на 48 часов', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: true } })
    guestLogin.mockResolvedValue({ data: { access_token: token, role: 'participant', guest_until: '2026-10-12T09:00:00+00:00' } })
    show()
    const button = await screen.findByRole('button', { name: 'Войти гостем без почты' })
    expect(button).toBeDisabled()
    await userEvent.click(await screen.findByTestId('consent-terms'))
    await userEvent.click(screen.getByTestId('consent-pd_candidate'))
    await userEvent.click(button)
    await waitFor(() => expect(guestLogin).toHaveBeenCalledWith('participant', ['terms', 'pd_candidate']))
    expect(useAuthStore.getState().guestUntil).toBe('2026-10-12T09:00:00+00:00')
    expect(useAuthStore.getState().userId).toBe('g1')
  })

  it('вне демо-стенда гостевого входа нет', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: false } })
    show()
    expect(await screen.findByRole('button', { name: 'Получить код на email' })).toBeInTheDocument()
    expect(screen.queryByTestId('guest-entry')).not.toBeInTheDocument()
  })

  it('продление сессии сохраняет срок гостя, новый аккаунт его сбрасывает', () => {
    useAuthStore.getState().setAuth(token, 'participant', '2026-10-12T09:00:00+00:00')
    useAuthStore.getState().setAuth(token, 'participant')
    expect(useAuthStore.getState().guestUntil).toBe('2026-10-12T09:00:00+00:00')
    const other = `x.${btoa(JSON.stringify({ sub: 'p2', exp: 4102444800 }))}.y`
    useAuthStore.getState().setAuth(other, 'participant')
    expect(useAuthStore.getState().guestUntil).toBeNull()
  })
})
