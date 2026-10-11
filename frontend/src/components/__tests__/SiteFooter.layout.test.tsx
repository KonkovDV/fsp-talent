import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { SiteFooter } from '../chrome'

// Regression: an `auto` column sized to the link list squeezed the legal text to ~74px at 1280+.
describe('SiteFooter layout', () => {
  it('keeps both footer columns shrinkable and lets long words wrap', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>)
    const grid = screen.getByTestId('site-footer-grid')
    expect(grid.className).not.toMatch(/_auto\]/)
    expect(grid.className).toContain('minmax(0,')
    const text = grid.firstElementChild as HTMLElement
    expect(text.className).toContain('min-w-0')
    expect(text.className).toContain('[overflow-wrap:anywhere]')
  })
})
