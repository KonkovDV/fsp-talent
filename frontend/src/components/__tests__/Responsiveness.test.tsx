import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Responsiveness from '../Responsiveness'

describe('отзывчивость компании на отклики', () => {
  it('под пятью откликами число не показывает', () => {
    render(<Responsiveness fact={{ shown: false, n: 3, note: 'мало данных', window_days: 90, within_days: 7 }} />)
    expect(screen.getByTestId('responsiveness')).toHaveTextContent('мало данных')
    expect(screen.getByTestId('responsiveness')).not.toHaveTextContent('%')
  })

  it('показывает нижнюю границу, число откликов и медиану', () => {
    render(<Responsiveness fact={{ shown: true, n: 12, count: 9, lower: 0.512, median_days: 2.5, window_days: 90, within_days: 7 }} />)
    const line = screen.getByTestId('responsiveness')
    expect(line).toHaveTextContent('не реже 51 %')
    expect(line).toHaveTextContent('по 12 откликам за 90 дней')
    expect(line).toHaveTextContent('через 2,5 дн.')
  })

  it('без данных ничего не рисует', () => {
    const { container } = render(<Responsiveness fact={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
