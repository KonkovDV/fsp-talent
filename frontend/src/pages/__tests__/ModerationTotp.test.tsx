import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Moderation from '../employer/Moderation'

const { get, post, assessmentBlueprint } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), assessmentBlueprint: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, api: { ...actual.api, get, post }, assessmentBlueprint }
})

const AI = { kinds: [], items: [], can_edit: false, in_use: null }
const reply = (factor: object, staff = true) => (url: string) => {
  if (url === '/employer/me/staff') return Promise.resolve({ data: { is_staff: staff } })
  if (url === '/moderation/totp') return Promise.resolve({ data: factor })
  if (url === '/moderation/complaints') return Promise.resolve({ data: [] })
  if (url === '/moderation/ai-providers') return Promise.resolve({ data: AI })
  return Promise.resolve({ data: { model_ready: false, items: [] } })
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><Moderation /></QueryClientProvider>)
}

describe('второй фактор стола модерации', () => {
  it('пока код не введён, стол не запрашивает жалобы; после кода открывается', async () => {
    assessmentBlueprint.mockResolvedValue({ data: { specializations: {} } })
    get.mockImplementation(reply({ enrolled: true, unlocked: false, unlocked_until: null }))
    post.mockResolvedValue({ data: { enrolled: true, unlocked: true, unlocked_until: '2026-10-10T09:15:00Z' } })
    show()
    await userEvent.type(await screen.findByLabelText('Код из приложения'), '12a3456')
    expect(get).not.toHaveBeenCalledWith('/moderation/complaints')
    await userEvent.click(screen.getByRole('button', { name: 'Открыть стол' }))
    expect(post).toHaveBeenCalledWith('/moderation/totp', { code: '123456' })
    expect(await screen.findByText('Жалоб нет')).toBeInTheDocument()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/moderation/complaints'))
  })

  it('без включённого фактора стол открыт сразу', async () => {
    get.mockImplementation(reply({ enrolled: false, unlocked: false, unlocked_until: null }))
    show()
    expect(await screen.findByText('Жалоб нет')).toBeInTheDocument()
    expect(screen.queryByTestId('totp-form')).not.toBeInTheDocument()
  })

  it('обычному работодателю не зовёт totp и показывает «недоступен»', async () => {
    get.mockImplementation(reply({ enrolled: false, unlocked: false, unlocked_until: null }, false))
    show()
    expect(await screen.findByText('Раздел недоступен')).toBeInTheDocument()
    expect(get).not.toHaveBeenCalledWith('/moderation/totp')
    expect(screen.queryByTestId('totp-form')).not.toBeInTheDocument()
  })
})
