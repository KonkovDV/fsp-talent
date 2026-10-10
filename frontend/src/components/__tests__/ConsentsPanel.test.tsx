import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ConsentsPanel from '../ConsentsPanel'

const { myConsents, withdrawConsent } = vi.hoisted(() => ({
  myConsents: vi.fn(),
  withdrawConsent: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, myConsents, withdrawConsent }
})

function renderPage(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  myConsents.mockResolvedValue({ data: [{
    kind: 'pd_candidate', title: 'Обработка данных', version: '1.0', required: true, active: true,
    given_at: '2026-01-02T00:00:00Z', accepted_version: '1.0', outdated: false,
    if_withdrawn: [
      { code: 'hide_card', text: 'Карточка сразу пропадёт из поиска.' },
      { code: 'erase_in_30_days', text: 'Данные будут стёрты в течение 30 дней.' },
    ],
  }] })
  withdrawConsent.mockResolvedValue({ data: { effects: [], effect_items: [] } })
})

describe('отзыв согласия', () => {
  it('перед отзывом показывает, что изменится', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPage(<ConsentsPanel />)
    await userEvent.click(await screen.findByRole('button', { name: 'Отозвать' }))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Карточка сразу пропадёт из поиска.'))
    expect(withdrawConsent).not.toHaveBeenCalled()
    confirm.mockRestore()
  })
})
