import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import JuryQuickStart from '../JuryQuickStart'
import JuryPage from '../../pages/JuryPage'

describe('контраст (ST-11, ST-12)', () => {
  it('мелкий текст блока «Войти как жюри» не полупрозрачнее 95 % белого', () => {
    const { container } = render(<MemoryRouter><JuryQuickStart /></MemoryRouter>)
    expect(container.querySelector('.text-white\\/80, .text-white\\/85')).toBeNull()
  })

  it('ссылки «Открыть» в шагах «Три пути» подчёркнуты всегда, а не только при наведении', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><JuryPage /></MemoryRouter></QueryClientProvider>)
    const steps = screen.getAllByRole('link', { name: 'Открыть' }).filter(a => a.classList.contains('text-accent'))
    expect(steps.length).toBeGreaterThanOrEqual(10)
    for (const a of steps) expect(a.classList.contains('underline')).toBe(true)
  })
})
