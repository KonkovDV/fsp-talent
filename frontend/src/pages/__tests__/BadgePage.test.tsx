import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BadgePage from '../BadgePage'

const verifyCredential = vi.fn()
vi.mock('../../api/client', () => ({
  verifyCredential: (c: unknown) => verifyCredential(c),
  credentialStatus: () => Promise.reject(new Error('нет')),
  issuerDid: () => Promise.resolve({ data: { id: 'did:web:example' } }),
}))
vi.mock('../../components/PublicShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))

const card = JSON.stringify({ type: ['VerifiableCredential'], credentialSubject: { achievement: { name: 'Чемпионат', year: 2019 } } })

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><BadgePage /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => { verifyCredential.mockReset() })

describe('проверка удостоверения', () => {
  it('при неверной подписи показывает ошибку и не показывает поля документа как факты', async () => {
    verifyCredential.mockResolvedValue({ data: { valid: false } })
    renderPage()
    const box = screen.getByLabelText('JSON удостоверения')
    await userEvent.click(box)
    await userEvent.paste(card)
    await userEvent.click(screen.getByRole('button', { name: 'Проверить' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/подпись не сходится/)
    expect(screen.queryByText('2019')).not.toBeInTheDocument()
  })

  it('при верной подписи показывает поля, а правка JSON снимает старый результат', async () => {
    verifyCredential.mockResolvedValue({ data: { valid: true } })
    renderPage()
    const box = screen.getByLabelText('JSON удостоверения')
    await userEvent.click(box)
    await userEvent.paste(card)
    await userEvent.click(screen.getByRole('button', { name: 'Проверить' }))
    expect(await screen.findByText('2019')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(/подпись сходится/)
    await userEvent.type(box, ' ')
    expect(screen.queryByText('2019')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
