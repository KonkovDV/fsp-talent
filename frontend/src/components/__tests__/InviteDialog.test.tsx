import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import InviteDialog from '../InviteDialog'

vi.mock('../../api/client', () => ({
  createOffer: vi.fn(),
  previewOffer: vi.fn(() => Promise.resolve({ data: {} })),
  apiError: () => 'Приглашение не отправлено',
  getLimits: vi.fn(() => Promise.resolve({ min_monthly_gross: 27093 })),
}))

function renderDialog() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <InviteDialog candidateId="11111111-1111-1111-1111-111111111111" onClose={() => undefined} />
    </QueryClientProvider>,
  )
}

describe('приглашение', () => {
  it('без вилки не отправляется и подписывает зарплату до вычета НДФЛ', async () => {
    renderDialog()
    expect(screen.getByText(/до вычета НДФЛ/)).toBeInTheDocument()
    const send = screen.getByRole('button', { name: 'Отправить приглашение' })
    expect(send).toBeEnabled()
    await userEvent.clear(screen.getByRole('spinbutton', { name: 'От' }))
    expect(send).toBeDisabled()
  })

  it('включает кнопку, когда вилка снова целая', async () => {
    renderDialog()
    const from = screen.getByRole('spinbutton', { name: 'От' })
    await userEvent.clear(from)
    await userEvent.type(from, '180000')
    expect(screen.getByRole('button', { name: 'Отправить приглашение' })).toBeEnabled()
  })

  it('берёт МРОТ из API и не пропускает вилку ниже него', async () => {
    renderDialog()
    await screen.findByRole('button', { name: 'Отправить приглашение' })
    await new Promise(r => setTimeout(r, 0))
    const from = screen.getByRole('spinbutton', { name: 'От' })
    await userEvent.clear(from)
    await userEvent.type(from, '20000')
    const to = screen.getByRole('spinbutton', { name: 'До' })
    await userEvent.clear(to)
    await userEvent.type(to, '30000')
    await userEvent.type(screen.getByLabelText(/Должность/i), 'Backend')
    await userEvent.click(screen.getByRole('button', { name: 'Отправить приглашение' }))
    expect(await screen.findByText(/не ниже МРОТ 27\s093 ₽/)).toBeInTheDocument()
  })
})

describe('приглашение: активный оффер (409)', () => {
  it('после 409 кнопка отправки выключена', async () => {
    const client = await import('../../api/client')
    vi.mocked(client.createOffer).mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Активный оффер этому кандидату уже есть' } } })
    renderDialog()
    await userEvent.type(screen.getByLabelText(/Должность/i), 'Backend')
    await userEvent.type(screen.getByLabelText(/связ/i), '@hr_team')
    const send = screen.getByRole('button', { name: 'Отправить приглашение' })
    await userEvent.click(send)
    await screen.findByText('Приглашение не отправлено')
    expect(send).toBeDisabled()
  })
})
