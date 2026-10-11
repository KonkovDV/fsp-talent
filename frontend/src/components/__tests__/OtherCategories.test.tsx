import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import OtherCategories from '../OtherCategories'

const show = (primary: string | null, confirmations: { specialization: string; grade: string }[]) =>
  render(<MemoryRouter><OtherCategories primary={primary} confirmations={confirmations} /></MemoryRouter>)

describe('OtherCategories', () => {
  it('lists only confirmations outside the survey category', () => {
    show('backend', [{ specialization: 'backend', grade: 'middle' }, { specialization: 'security', grade: 'junior' }])
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(1)
    expect(items[0].textContent).toContain('подтверждено тестом')
    expect(screen.getByRole('link', { name: /другой специализации/ }).getAttribute('href')).toBe('/candidate/assessment')
  })

  it('says there is only the survey category when nothing else is confirmed', () => {
    show('backend', [{ specialization: 'backend', grade: 'middle' }])
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText('Пока только категория из опроса.')).toBeTruthy()
  })

  it('renders nothing before the survey', () => {
    const { container } = show(null, [])
    expect(container.textContent).toBe('')
  })
})
