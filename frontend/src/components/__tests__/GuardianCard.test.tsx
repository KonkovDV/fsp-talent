import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import GuardianCard from '../GuardianCard'

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, askGuardian: vi.fn() }
})

function renderCard(demoLink: string | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <GuardianCard sentTo="parent@example.com" demoLink={demoLink} />
    </QueryClientProvider>,
  )
}

describe('согласие представителя', () => {
  it('показывает ссылку, которую стенд отдал самому участнику', () => {
    const link = 'https://stand.example/guardian#token=abc'
    renderCard(link)
    expect(screen.getByRole('link', { name: link })).toHaveAttribute('href', link)
    expect(screen.getByText(/письма отсюда не уходят/)).toBeInTheDocument()
  })

  it('без ссылки не предлагает подтверждение на экране', () => {
    renderCard(null)
    expect(screen.queryByText(/письма отсюда не уходят/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})