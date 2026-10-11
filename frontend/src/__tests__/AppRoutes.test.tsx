import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { useAuthStore } from '../store/authStore'

// Every request hangs: the pages stay in their loading state, which is all a provider check needs.
vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client')
  const hang = () => new Promise(() => {})
  const stubbed: Record<string, unknown> = {}
  for (const [name, value] of Object.entries(actual)) stubbed[name] = typeof value === 'function' && name !== 'apiError' ? hang : value
  stubbed.publicStats = () => Promise.resolve({ data: { candidates: 703, with_fsp: 255, families: 22, companies: 16 } })
  stubbed.api = { get: hang, post: hang, put: hang, patch: hang, delete: hang, interceptors: actual.api.interceptors, defaults: actual.api.defaults }
  return stubbed
})

let errors: string[] = []
beforeEach(() => {
  errors = []
  vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => { errors.push(args.map(String).join(' ')) })
})
afterEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ token: null, userRole: null, needsRenew: false, example: false })
})

function open(path: string) {
  window.history.pushState({}, '', path)
  return render(<App />)
}

const noProviderErrors = () => expect(errors.filter(e => /QueryClient|must be used within|context/i.test(e))).toEqual([])

describe('реальная маршрутизация App', () => {
  it('главная рендерится вне QueryShell: контент, «Войти как жюри» и живые числа', async () => {
    open('/')
    expect(await screen.findByText(/Приглашайте разработчиков по/)).toBeInTheDocument()
    expect(screen.getByText('Войти как жюри')).toBeInTheDocument()
    expect(await screen.findByTestId('stand-counts')).toHaveTextContent('703')
    expect(screen.getByRole('link', { name: 'API (Swagger)' })).toHaveAttribute('href', '/docs')
    noProviderErrors()
  })

  it('/method рендерится через App', async () => {
    open('/method')
    await waitFor(() => expect(document.querySelector('#main, main')).not.toBeNull(), { timeout: 5000 })
    noProviderErrors()
  })

  it.each(['/employer', '/employer/needs', '/employer/integrations', '/employer/company'])('%s рендерится через App', async path => {
    useAuthStore.setState({ token: 'x.e30.x', userRole: 'employer', needsRenew: false, example: false })
    const { container } = open(path)
    await waitFor(() => expect(container.querySelector('h1')).not.toBeNull(), { timeout: 5000 })
    noProviderErrors()
  })
})
