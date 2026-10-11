import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RegisterPage from '../RegisterPage'
import PrivacyPage from '../PrivacyPage'
import { SiteFooter } from '../../components/chrome'

const { publicDemo, legalDocuments, legalDocument } = vi.hoisted(() => ({
  publicDemo: vi.fn(), legalDocuments: vi.fn(), legalDocument: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, legalDocuments, legalDocument }
})

const policy = {
  kind: 'privacy_policy', title: 'Политика обработки персональных данных', version: '1.0', required: false,
  consent: false, roles: ['participant', 'employer'], sha256: 'c'.repeat(64),
  body_md: '# Политика обработки персональных данных\n\n**1. Оператор.** На демонстрационном стенде оператор — команда-участник хакатона.\n\n**8. Сроки хранения.** До отзыва согласия.',
}

function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  publicDemo.mockReset()
  legalDocuments.mockResolvedValue({ data: [] })
  legalDocument.mockResolvedValue({ data: policy })
})

describe('плашка демо-стенда (сервер вне России)', () => {
  it('на демо-стенде видна на /register, рядом ссылка на политику', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: true, mail_console: true } })
    show('/register')
    const notice = await screen.findByTestId('demo-stand-notice')
    expect(notice).toHaveTextContent('за пределами России')
    expect(notice).toHaveTextContent('Настоящие персональные данные сюда не вводите')
    expect(screen.getByRole('link', { name: 'политике обработки персональных данных' })).toHaveAttribute('href', '/privacy')
  })

  it('в промышленном контуре (DEMO_MODE выключен) плашки нет', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: false, mail_console: false } })
    show('/register')
    expect(await screen.findByRole('button', { name: 'Получить код на email' })).toBeInTheDocument()
    await new Promise(r => setTimeout(r, 0))
    expect(screen.queryByTestId('demo-stand-notice')).not.toBeInTheDocument()
  })

  it('если /public/demo не ответил, плашки нет', async () => {
    publicDemo.mockRejectedValue(new Error('offline'))
    show('/register')
    expect(await screen.findByRole('button', { name: 'Получить код на email' })).toBeInTheDocument()
    expect(screen.queryByTestId('demo-stand-notice')).not.toBeInTheDocument()
  })
})

describe('страница /privacy', () => {
  it('открывается и показывает текст политики из публичного эндпоинта согласий', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: true } })
    show('/privacy')
    expect(await screen.findByTestId('privacy-policy')).toHaveTextContent('команда-участник хакатона')
    expect(screen.getByText('1. Оператор.').tagName).toBe('STRONG')
    expect(screen.getByRole('heading', { level: 1, name: 'Политика обработки персональных данных' })).toBeInTheDocument()
    expect(legalDocument).toHaveBeenCalledWith('privacy_policy')
    expect(await screen.findByTestId('demo-stand-notice')).toBeInTheDocument()
  })

  it('ссылка на /privacy есть в подвале', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Политика обработки данных' })).toHaveAttribute('href', '/privacy')
  })
})
