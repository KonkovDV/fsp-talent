import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Company from '../employer/Company'

const m = vi.hoisted(() => ({
  myConsents: vi.fn(), getEmployerMe: vi.fn(), getReputation: vi.fn(),
}))
vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  const never = () => new Promise(() => {})
  return {
    ...actual, ...m,
    api: { get: never, post: never, delete: never, put: never, patch: never },
  }
})

describe('согласия в кабинете работодателя', () => {
  it('показывает версию и дату принятого документа', async () => {
    m.getEmployerMe.mockReturnValue(new Promise(() => {}))
    m.getReputation.mockReturnValue(new Promise(() => {}))
    m.myConsents.mockResolvedValue({ data: [{
      kind: 'pd_employer', title: 'Обработка данных работодателя', version: '1.3', required: true, active: true,
      given_at: '2026-10-10T00:00:00Z', accepted_version: '1.2', outdated: true, if_withdrawn: [],
    }] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><Company /></MemoryRouter></QueryClientProvider>)
    const box = screen.getByTestId('employer-consents')
    expect(await within(box).findByText(/дано 10\.10\.2026, версия 1\.2 \(текст обновлён\)/)).toBeInTheDocument()
  })
})
