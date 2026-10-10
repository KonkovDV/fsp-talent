import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AiNote from '../AiNote'

const { getAiNote } = vi.hoisted(() => ({ getAiNote: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, getAiNote }
})

function wrap() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><AiNote needId="n1" candidateId="c1" /></QueryClientProvider>)
}

describe('мнение ИИ по карточке', () => {
  it('показывает пункты с основаниями и пометку, что балл не меняется', async () => {
    getAiNote.mockResolvedValue({ data: {
      summary: 'Мидл с подтверждённым грейдом.', dropped: 1, provider: 'yandex', model: 'yandexgpt/latest',
      generated_at: '2026-10-10T10:00:00Z', affects_score: false, cached: false,
      strengths: [{ text: 'Есть Python и SQL', facts: ['Есть из обязательных: Python, SQL'] }],
      risks: [{ text: 'Нет Kafka', facts: ['Нет из обязательных: Kafka'] }],
      questions: [{ text: 'Работали с очередями?', facts: ['Нет из обязательных: Kafka'] }],
    } })
    wrap()
    await userEvent.click(screen.getByRole('button', { name: /Мнение ИИ/ }))
    expect(await screen.findByText('Есть Python и SQL')).toBeInTheDocument()
    expect(getAiNote).toHaveBeenCalledWith('n1', 'c1')
    expect(screen.getByText(/Не влияет на балл и порядок/)).toBeInTheDocument()
    expect(screen.getByText(/YandexGPT/)).toBeInTheDocument()
    expect(screen.getByText('Работали с очередями?')).toBeInTheDocument()
    expect(screen.getByText(/Отброшено пунктов без опоры на факты: 1/)).toBeInTheDocument()
  })

  it('сообщает, когда ИИ недоступен', async () => {
    getAiNote.mockRejectedValue({ isAxiosError: true, response: { status: 503, data: { detail: 'ИИ-помощник не подключён' } } })
    wrap()
    await userEvent.click(screen.getByRole('button', { name: /Мнение ИИ/ }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
