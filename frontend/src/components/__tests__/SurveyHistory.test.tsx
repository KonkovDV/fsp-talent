import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('../../api/client', () => ({
  surveyHistory: () => Promise.resolve({ data: [
    { specialization: 'frontend', declared_grade: 'middle', experience_years: 3, created_at: '2026-10-11T10:00:00Z' },
    { specialization: 'backend', declared_grade: 'junior', experience_years: null, created_at: '2026-10-01T10:00:00Z' },
  ] }),
}))
import SurveyHistory from '../SurveyHistory'

describe('SurveyHistory', () => {
  it('lists every survey submit newest first, in Russian', async () => {
    render(<QueryClientProvider client={new QueryClient()}><SurveyHistory /></QueryClientProvider>)
    const items = await screen.findAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0].textContent).toContain('опыт 3')
    expect(items[0].textContent).not.toContain('frontend')
  })
})
