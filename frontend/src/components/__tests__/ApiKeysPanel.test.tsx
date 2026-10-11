import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ApiKeysPanel, { exportExamples } from '../ApiKeysPanel'

const { get, post, del } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }))
vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, api: { get, post, delete: del } }
})

function wrap() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ApiKeysPanel /></QueryClientProvider>)
}

describe('API-ключи', () => {
  it('примеры кладут ключ в заголовок, не в адрес', () => {
    const ex = exportExamples('https://s.test', 'fspk_x')
    expect(ex.json).toBe('curl -H "X-API-Key: fspk_x" "https://s.test/api/v1/employer/integrations/export?fmt=json"')
    expect(ex.csv).toContain('?fmt=csv')
    expect(ex.csv.split('"')[3]).not.toContain('fspk_x')
  })

  it('показывает новый ключ один раз и список по префиксу', async () => {
    get.mockResolvedValue({ data: [{ id: '1', prefix: 'fspk_abcd1234_…', label: 'ATS', created_at: '2026-10-11T10:00:00Z', last_used_at: null, revoked_at: null }] })
    post.mockResolvedValue({ data: { id: '2', prefix: 'fspk_ffff0000_…', label: null, created_at: '2026-10-11T10:00:00Z', last_used_at: null, revoked_at: null, key: 'fspk_ffff0000_secretsecret' } })
    wrap()
    expect(await screen.findByText('fspk_abcd1234_…')).toBeInTheDocument()
    expect(screen.queryByTestId('api-key-once')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Создать ключ' }))
    expect(await screen.findByTestId('api-key-once')).toHaveTextContent('fspk_ffff0000_secretsecret')
    expect(screen.getByTestId('example-json')).toHaveTextContent('X-API-Key: fspk_ffff0000_secretsecret')
  })

  it('отзывает ключ', async () => {
    get.mockResolvedValue({ data: [{ id: '1', prefix: 'fspk_abcd1234_…', label: null, created_at: '2026-10-11T10:00:00Z', last_used_at: null, revoked_at: null }] })
    del.mockResolvedValue({ data: { revoked: true } })
    wrap()
    fireEvent.click(await screen.findByRole('button', { name: 'Отозвать' }))
    await vi.waitFor(() => expect(del).toHaveBeenCalledWith('/employer/integrations/keys/1'))
  })
})
