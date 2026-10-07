import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import InviteDialog from '../InviteDialog'

vi.mock('../../api/client', () => ({
  createOffer: vi.fn(),
  previewOffer: vi.fn(() => Promise.resolve({ data: {} })),
  apiError: () => 'Приглашение не отправлено',
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
})
