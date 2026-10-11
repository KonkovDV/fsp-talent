import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import LegalPage from '../LegalPage'

const { legalDocuments, legalProcessor } = vi.hoisted(() => ({
  legalDocuments: vi.fn(),
  legalProcessor: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, legalDocuments, legalProcessor }
})

vi.mock('../../components/PublicShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const docs = [{
  kind: 'privacy_policy',
  title: 'Политика',
  roles: ['participant', 'employer'],
  version: '1.0',
  sha256: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
  required: true,
  consent: false,
}]

describe('страница /legal', () => {
  it('на узкой ширине показывает карточки со SHA, на широкой — таблицу', async () => {
    legalDocuments.mockResolvedValue({ data: docs })
    legalProcessor.mockResolvedValue({ data: { enabled: false } })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter><LegalPage /></MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByLabelText('Список документов')).toBeInTheDocument()
    expect(screen.getByLabelText('Таблица документов')).toBeInTheDocument()
    expect(screen.getAllByText(/abcdef0123456789/).length).toBeGreaterThanOrEqual(1)
    const table = screen.getByLabelText('Таблица документов')
    expect(table.className).toMatch(/overflow-x-auto/)
    expect(table.className).toMatch(/min-w-full/)
  })
})
