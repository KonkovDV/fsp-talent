import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import EvaluatePage from '../EvaluatePage'
import SelfLabel, { STORAGE_KEY, type BlindSheet } from '../evaluate/SelfLabel'
import sheetJson from '../../data/blindSheet.json'

const { evaluatePairs } = vi.hoisted(() => ({ evaluatePairs: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, evaluatePairs }
})

const sheet = sheetJson as unknown as BlindSheet
const firstNeed = sheet.pairs.filter(p => p.need_id === sheet.needs[0].id)

const report = {
  pairs: 8, needs: 1, judged_needs: 1, sha256: 'b'.repeat(64),
  rows: [
    { method: 'full', title: 'ФСП Талант: оценка соответствия', ndcg10: 0.91, ndcg_ci: [0.91, 0.91], p10: 0.5, p5: 0.8, map: 0.9 },
    { method: 'keyword', title: 'Базовая линия «по резюме»: заявленные навыки и грейд', ndcg10: 0.74, ndcg_ci: null, p10: 0.5, p5: 0.6, map: 0.7 },
    { method: 'random', title: 'Случайный порядок', ndcg10: 0.55, ndcg_ci: null, p10: 0.5, p5: 0.4, map: 0.5 },
  ],
  per_need: [],
  paired_delta: { mean: 0.17, ci: [0.17, 0.17], needs: 1, model_better: 1, resume_better: 0 },
}

function wrap(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter>{node}</MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  window.localStorage.clear()
  evaluatePairs.mockReset()
})

describe('«Разметить самому»', () => {
  it('открывается по умолчанию и грузит слепой лист', async () => {
    wrap(<EvaluatePage />)
    expect(screen.getByRole('tab', { name: 'Разметить самому' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByLabelText('Потребность')).toBeInTheDocument()
    expect(screen.getAllByRole('option')).toHaveLength(sheet.needs.length)
  })

  it('показывает карточку без балла и источника, а по восьмой оценке — итог', async () => {
    evaluatePairs.mockResolvedValue({ data: report })
    wrap(<SelfLabel sheet={sheet} />)
    await userEvent.click(screen.getByRole('button', { name: 'Начать' }))
    expect(screen.getByTestId('self-need-card')).toHaveTextContent('Python, SQL')
    const card = screen.getByTestId('self-candidate-card')
    expect(card).toHaveTextContent(firstNeed[0].card.split('. ')[0].replace('Специализация: ', ''))
    expect(card).not.toHaveTextContent(/балл|модел|резюме-топ|c\d{2,}/i)
    expect(screen.getByTestId('self-progress')).toHaveTextContent(`Карточка 1 из ${firstNeed.length}`)
    for (const v of [0, 1, 2, 3]) expect(screen.getByRole('button', { name: new RegExp(`^Оценка ${v} — `) })).toBeInTheDocument()

    // половина кнопками, половина клавишами
    const plan = [3, 2, 0, 1, 3, 0, 2, 1]
    for (const [i, v] of plan.entries()) {
      if (i % 2) await userEvent.keyboard(String(v))
      else await userEvent.click(screen.getByRole('button', { name: new RegExp(`^Оценка ${v} — `) }))
      if (i < plan.length - 1) expect(screen.getByTestId('self-progress')).toHaveTextContent(`Карточка ${i + 2} из`)
    }

    expect(evaluatePairs).toHaveBeenCalledTimes(1)
    const lines = (evaluatePairs.mock.calls[0][0] as string).split('\n').map(l => JSON.parse(l))
    expect(lines).toHaveLength(8)
    expect(lines.map(l => l.label).sort()).toEqual([...plan].sort())
    expect(lines[0]).toEqual({
      need: { id: sheet.needs[0].id, role: sheet.needs[0].role, grade: sheet.needs[0].grade, skills: sheet.needs[0].skills },
      candidate_id: firstNeed[0].candidate_id, candidate: { observed: firstNeed[0].observed }, label: 3,
    })

    const table = await screen.findByTestId('self-table')
    expect(within(table).getByText('Наша модель')).toBeInTheDocument()
    expect(within(table).getByText('0,80')).toBeInTheDocument()
    expect(within(table).getByText('0,74')).toBeInTheDocument()
    expect(screen.getByTestId('self-delta')).toHaveTextContent('+0,17')
    expect(screen.getByTestId('self-caveat')).toHaveTextContent('Выборка маленькая')
    expect(screen.getByRole('button', { name: 'Ещё одна потребность' })).toBeInTheDocument()

    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY)!)
    expect(Object.keys(saved.labels)).toHaveLength(8)
  })

  it('«Готово» посреди листа отправляет то, что есть; оценки переживают перезагрузку', async () => {
    evaluatePairs.mockResolvedValue({ data: { ...report, pairs: 2 } })
    const first = wrap(<SelfLabel sheet={sheet} />)
    await userEvent.click(screen.getByRole('button', { name: 'Начать' }))
    await userEvent.keyboard('3')
    await userEvent.keyboard('9')
    await userEvent.keyboard('1')
    expect(screen.getByTestId('self-progress')).toHaveTextContent('Карточка 3 из 8 · всего оценено 2')
    await userEvent.click(screen.getByRole('button', { name: 'Назад' }))
    expect(screen.getByTestId('self-progress')).toHaveTextContent('Карточка 2 из 8')
    await userEvent.click(screen.getByRole('button', { name: 'Готово' }))
    expect((evaluatePairs.mock.calls[0][0] as string).split('\n')).toHaveLength(2)
    expect(await screen.findByTestId('self-caveat')).toHaveTextContent('2 оценки')
    first.unmount()

    wrap(<SelfLabel sheet={sheet} />)
    expect(screen.getByTestId('self-progress')).toHaveTextContent('Карточка 3 из 8 · всего оценено 2')
    await userEvent.click(screen.getByRole('button', { name: 'Стереть мои оценки' }))
    expect(screen.getByRole('button', { name: 'Начать' })).toBeInTheDocument()
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY)!).labels).toEqual({})
  })

})

describe('разметка без релевантных (раньше 422)', () => {
  it('все оценки 0: запрос не уходит, объясняем, что нужно', async () => {
    wrap(<SelfLabel sheet={sheet} />)
    await userEvent.click(screen.getByRole('button', { name: 'Начать' }))
    for (let i = 0; i < firstNeed.length; i++) await userEvent.keyboard('0')
    expect(await screen.findByTestId('self-no-relevant')).toBeInTheDocument()
    expect(evaluatePairs).not.toHaveBeenCalled()
  })
})
