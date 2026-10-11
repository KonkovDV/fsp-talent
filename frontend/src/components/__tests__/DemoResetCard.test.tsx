import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const reset = vi.fn(() => Promise.resolve({ data: { reset: true } }))
vi.mock('../../api/client', () => ({ resetMyDemo: () => reset(), apiError: (_: unknown, m: string) => m }))
import DemoResetCard from '../DemoResetCard'

const wrap = () => render(<QueryClientProvider client={new QueryClient()}><DemoResetCard /></QueryClientProvider>)

describe('DemoResetCard', () => {
  it('asks first and does nothing when the juror cancels', () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    wrap()
    fireEvent.click(screen.getByRole('button', { name: 'Начать заново (демо)' }))
    expect(reset).not.toHaveBeenCalled()
  })
  it('resets after the confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(true)
    wrap()
    fireEvent.click(screen.getByRole('button', { name: 'Начать заново (демо)' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Готово'))
    expect(reset).toHaveBeenCalledTimes(1)
  })
})
