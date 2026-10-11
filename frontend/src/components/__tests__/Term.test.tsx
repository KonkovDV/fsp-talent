import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import Term from '../Term'
import JuryPage from '../../pages/JuryPage'

describe('простые слова, термин в подсказке (JS-01)', () => {
  it('Term показывает слова и прячет термин в title, доступный с клавиатуры', () => {
    render(<Term term="BM25">Поиск по ключевым словам</Term>)
    const node = screen.getByText('Поиск по ключевым словам')
    expect(node).toHaveAttribute('title', 'Термин: BM25')
    expect(node).toHaveAttribute('tabindex', '0')
  })

  it('на /jury жаргон не стоит в видимом тексте', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={client}><MemoryRouter><JuryPage /></MemoryRouter></QueryClientProvider>,
    )
    const clone = container.cloneNode(true) as HTMLElement
    const visible = clone.textContent ?? ''
    for (const jargon of ['Симпсон', 'did:web', 'BM25', 'nDCG', 'LCB', 'θ', 'κ']) {
      expect(visible).not.toContain(jargon)
    }
    expect(container.querySelector('abbr[title="Термин: BM25"]')).not.toBeNull()
  })
})
