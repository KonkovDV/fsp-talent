import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import StandCounts from '../StandCounts'
import { SiteFooter } from '../chrome'

const { publicStats } = vi.hoisted(() => ({ publicStats: vi.fn() }))
vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicStats }
})

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>)
}

describe('StandCounts', () => {
  it('shows the four totals from the API', async () => {
    publicStats.mockResolvedValue({ data: { candidates: 703, with_fsp: 255, families: 22, companies: 16 } })
    wrap(<StandCounts />)
    expect(await screen.findByText('703')).toBeInTheDocument()
    expect(screen.getByText('255')).toBeInTheDocument()
    expect(screen.getByText('семейств заданий')).toBeInTheDocument()
  })
  it('shows nothing when the API fails', async () => {
    publicStats.mockRejectedValue(new Error('down'))
    const { container } = wrap(<StandCounts />)
    await new Promise(r => setTimeout(r, 20))
    expect(container.querySelector('[data-testid="stand-counts"]')).toBeNull()
  })
  it('footer links to the API docs', () => {
    wrap(<SiteFooter />)
    expect(screen.getByRole('link', { name: 'API (Swagger)' })).toHaveAttribute('href', '/docs')
  })
})
