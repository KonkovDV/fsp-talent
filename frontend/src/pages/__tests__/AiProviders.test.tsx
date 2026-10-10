import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AiProviders from '../employer/AiProviders'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, api: { ...actual.api, get, post, delete: vi.fn() } }
})

const kinds = [
  { kind: 'gigachat', label: 'GigaChat (Сбер)', params: ['scope'], hint: 'Ключ авторизации', hosts: ['gigachat.devices.sberbank.ru'] },
  { kind: 'yandex', label: 'YandexGPT (Yandex AI Studio)', params: ['folder_id'], hint: 'API-ключ', hosts: ['llm.api.cloud.yandex.net'] },
]
const row = { id: 'a1', kind: 'yandex', kind_label: 'YandexGPT (Yandex AI Studio)', label: 'Яндекс', model: 'yandexgpt/latest', check_model: null, params: { folder_id: 'b1g' }, is_active: false, created_at: '2026-10-10T09:00:00Z', activated_at: null }

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><AiProviders /></QueryClientProvider>)
}

describe('ИИ-провайдер на столе модерации', () => {
  it('сохраняет провайдера из списка без поля адреса и включает его', async () => {
    get.mockResolvedValue({ data: { kinds, items: [row], can_edit: true, in_use: { source: 'env', kind: 'gigachat', model: 'GigaChat-2-Pro' } } })
    post.mockResolvedValue({ data: { ok: true } })
    show()
    expect(await screen.findByTestId('ai-in-use')).toHaveTextContent('GigaChat (Сбер), модель GigaChat-2-Pro (из настроек сервера)')
    expect(screen.queryByLabelText(/адрес|url/i)).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Провайдер'), 'yandex')
    await userEvent.type(screen.getByLabelText('Название'), 'Яндекс-2')
    await userEvent.type(screen.getByLabelText('Модель'), 'yandexgpt/latest')
    await userEvent.type(screen.getByLabelText('ID каталога Yandex Cloud'), 'b1gabc')
    await userEvent.type(screen.getByLabelText('Ключ'), 'AQVN')
    expect(screen.getByLabelText('Ключ')).toHaveAttribute('type', 'password')
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }))
    await waitFor(() => expect(post).toHaveBeenCalledWith('/moderation/ai-providers', {
      kind: 'yandex', label: 'Яндекс-2', model: 'yandexgpt/latest', check_model: null, secret: 'AQVN', params: { folder_id: 'b1gabc' },
    }))
    await userEvent.click(screen.getByRole('button', { name: 'Включить' }))
    expect(post).toHaveBeenCalledWith('/moderation/ai-providers/a1/activate')
  })

  it('без второго фактора форма ключей закрыта', async () => {
    get.mockResolvedValue({ data: { kinds, items: [row], can_edit: false, in_use: null } })
    show()
    expect(await screen.findByTestId('ai-locked')).toBeInTheDocument()
    expect(screen.queryByLabelText('Ключ')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Включить' })).not.toBeInTheDocument()
    expect(screen.getByTestId('ai-in-use')).toHaveTextContent('модель выключена')
  })
})
