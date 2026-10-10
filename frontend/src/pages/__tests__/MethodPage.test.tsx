import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { itemPsychometrics } from '../../api/client'
import MethodPage from '../MethodPage'

const empty = {
  spec: 'backend', randomesque: 5, answers: 0, max_share: 0, exposure_target: 0.4,
  cuts: [
    { grade: 'junior', cut: -1.5, information: 0.4, se_after_12: 0.2 },
    { grade: 'middle', cut: -0.5, information: 0.5, se_after_12: 0.18 },
  ],
  curve: [
    { theta: -3, information: 0.1 },
    { theta: 0, information: 0.5 },
    { theta: 3, information: 0.2 },
  ],
  families: [],
  parents: [{ family_id: 'py', title: 'Python', a: 1.2, levels: [{ level: 1, b: -1 }, { level: 3, b: 0.5 }] }],
}

const shown = {
  ...empty,
  answers: 100,
  max_share: 0.5,
  families: [
    { family_id: 'sql', title: 'SQL', answers: 20, cusum: 0, quarantined: 0, max_share: 0.2 },
    { family_id: 'py', title: 'Python', answers: 50, cusum: 1, quarantined: 0, max_share: 0.5 },
    { family_id: 'go', title: 'Go', answers: 10, cusum: 0, quarantined: 0, max_share: 0.1 },
    { family_id: 'js', title: 'JavaScript', answers: 20, cusum: 0, quarantined: 1, max_share: 0.2 },
  ],
}

vi.mock('../../api/client', () => ({
  itemPsychometrics: vi.fn(() => Promise.resolve({ data: empty })),
  methodWeights: vi.fn(() => Promise.reject(new Error('hidden'))),
  previewPublicExam: vi.fn(),
  apiError: () => 'ошибка',
}))

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter><MethodPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('страница методики', () => {
  beforeEach(() => {
    vi.mocked(itemPsychometrics).mockResolvedValue({ data: empty } as never)
  })

  it('показывает кривую, пороги грейда и пять цифр с командами', async () => {
    renderPage()
    const curve = await screen.findByRole('img', { name: /Кривая информации/ })
    expect(curve.querySelectorAll('line')).toHaveLength(3)
    expect(screen.getByText('91,5 %')).toBeInTheDocument()
    expect(screen.getByText('0,47')).toBeInTheDocument()
    expect(screen.getByText('0,22')).toBeInTheDocument()
    expect(screen.getByText('0 %')).toBeInTheDocument()
    expect(screen.getByText('65,8 %')).toBeInTheDocument()
    expect(screen.getAllByText(/python -m app.validation.assessment --n 2000 --seed 7/)).toHaveLength(7)
    expect(screen.getByRole('img', { name: 'Показов ещё нет' })).toBeInTheDocument()
    expect(screen.getByText(/максимальная доля одного ключа — 34 %/)).toBeInTheDocument()
    expect(screen.queryByText(/item_key|правильный ответ/)).not.toBeInTheDocument()
  })

  it('ставит столбцы по убыванию и подписывает первые три', async () => {
    vi.mocked(itemPsychometrics).mockResolvedValue({ data: shown } as never)
    renderPage()
    const chart = await screen.findByRole('img', { name: /Показы по семействам, максимум 50 %/ })
    expect([...chart.querySelectorAll('[data-family]')].map(node => node.getAttribute('data-family')))
      .toEqual(['py', 'js', 'sql', 'go'])
    expect(chart.querySelectorAll('text')).toHaveLength(3)
    expect(screen.getByText('50 % · 20 % · 20 %')).toBeInTheDocument()
  })

  it('подписывает первые три столбца и когда семейств много', async () => {
    const many = {
      ...shown,
      answers: 160,
      families: Array.from({ length: 16 }, (_, index) => ({
        family_id: `f${index}`,
        title: `Семейство ${index}`,
        answers: 16 - index,
        cusum: 0,
        quarantined: 0,
        max_share: (16 - index) / 160,
      })),
    }
    vi.mocked(itemPsychometrics).mockResolvedValue({ data: many } as never)
    renderPage()
    const chart = await screen.findByRole('img', { name: /Показы по семействам, максимум 10 %/ })
    expect(chart.querySelectorAll('text')).toHaveLength(3)
    expect([...chart.querySelectorAll('[data-family]')].slice(0, 3).map(node => node.getAttribute('data-family')))
      .toEqual(['f0', 'f1', 'f2'])
  })

  it('пишет долю на стенде, 34 % симуляции и цель 0,40', async () => {
    vi.mocked(itemPsychometrics).mockResolvedValue({ data: shown } as never)
    renderPage()
    expect(await screen.findByText(/Максимальная доля показов одного семейства: 50 % на стенде/)).toBeInTheDocument()
    expect(screen.getByText(/в симуляции 2000 кандидатов — 34 %/)).toBeInTheDocument()
    expect(screen.getByText(/Внутри специализации до 69 %/)).toBeInTheDocument()
    expect(screen.getByText(/Числа в задании каждый раз другие/)).toBeInTheDocument()
    expect(screen.getByText(/целевая доля одного ключа 0,40/)).toBeInTheDocument()
  })
})
