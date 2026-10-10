import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { searchCandidates } from '../../api/client'
import { exampleFixture, serverUnreachable } from '../../demoFallback'
import LoginPage from '../LoginPage'
import { useAuthStore } from '../../store/authStore'

const { publicDemo } = vi.hoisted(() => ({ publicDemo: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, publicJuryFree: vi.fn(), loginParticipant: vi.fn(), loginEmployer: vi.fn() }
})

beforeEach(() => {
  useAuthStore.getState().logout()
  publicDemo.mockRejectedValue(new AxiosError('offline'))
})

describe('пример, когда сервер молчит', () => {
  it('отличает тишину и шлюз от ответа приложения', () => {
    expect(serverUnreachable(new AxiosError('offline'))).toBe(true)
    expect(serverUnreachable({ response: { status: 503 } })).toBe(true)
    expect(serverUnreachable({ response: { status: 500 } })).toBe(false)
    expect(serverUnreachable({ response: { status: 401 } })).toBe(false)
    expect(serverUnreachable({ code: 'ERR_CANCELED' })).toBe(false)
    expect(exampleFixture('/public/demo')).toBeUndefined()
    expect(exampleFixture('/search/candidates')).toMatchObject({ total: 2 })
  })

  it('со входа открывает пример кабинета работодателя', async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    await userEvent.click(await screen.findByRole('button', { name: 'Пример кабинета работодателя' }))
    expect(useAuthStore.getState().example).toBe(true)
    expect(useAuthStore.getState().userRole).toBe('employer')
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('в примере чтение идёт из заготовки, запись отклоняется', async () => {
    useAuthStore.getState().enterExample('employer')
    const found = await searchCandidates({})
    expect(found.data.items).toHaveLength(2)
    expect(found.data.items[0].match.reply.label).toBe('высокая')
    const { api } = await import('../../api/client')
    await expect(api.post('/offers/', { candidate_id: 'x' })).rejects.toMatchObject({
      response: { status: 409 },
    })
  })
})
