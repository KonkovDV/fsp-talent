import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '../LoginPage'

const { publicDemo, publicJuryFree, loginParticipant } = vi.hoisted(() => ({
  publicDemo: vi.fn(), publicJuryFree: vi.fn(), loginParticipant: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, publicJuryFree, loginParticipant, loginEmployer: vi.fn() }
})

beforeEach(() => {
  publicDemo.mockResolvedValue({ data: { demo_mode: true } })
  publicJuryFree.mockRejectedValue(new Error('offline'))
})

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('вход', () => {
  it('кладёт в форму аккаунт, в который дольше всех не входили', async () => {
    publicJuryFree.mockResolvedValue({ data: { email: 'jury4@demo.talent' } })
    renderLogin()
    await userEvent.click(await screen.findByRole('button', { name: 'Взять свободный аккаунт жюри' }))
    expect(screen.getByLabelText('Email')).toHaveValue('jury4@demo.talent')
    expect(screen.getByLabelText('Пароль')).toHaveValue('demo12345')
  })

  it('без ответа стенда берёт случайный аккаунт жюри', async () => {
    renderLogin()
    await userEvent.click(await screen.findByRole('button', { name: 'Взять свободный аккаунт жюри' }))
    expect((screen.getByLabelText('Email') as HTMLInputElement).value).toMatch(/^jury([1-9]|10)@demo\.talent$/)
    expect(screen.getByLabelText('Пароль')).toHaveValue('demo12345')
  })

  it('помечает демо-доступ для жюри без обещания ночного сброса', async () => {
    renderLogin()
    expect(await screen.findByText(/данные синтетические/)).toBeInTheDocument()
    expect(screen.queryByText(/сбросить кнопкой/)).not.toBeInTheDocument()
    expect(screen.queryByText(/сбрасывается каждую ночь/)).not.toBeInTheDocument()
  })

  it('«Войти как жюри» сразу входит свободным аккаунтом (BR-08)', async () => {
    publicJuryFree.mockResolvedValue({ data: { email: 'jury7@demo.talent' } })
    loginParticipant.mockResolvedValue({ data: { access_token: 't' } })
    renderLogin()
    await userEvent.click(await screen.findByRole('button', { name: 'Войти как жюри' }))
    expect(loginParticipant).toHaveBeenCalledWith('jury7@demo.talent', 'demo12345')
  })

  it('подсказки входа не противоречат друг другу (BR-08)', async () => {
    renderLogin()
    expect(await screen.findByText(/логин FSP001, пароль test \(вводится на странице провайдера\)/)).toBeInTheDocument()
    expect(screen.getAllByText(/данные синтетические/)).toHaveLength(1)
    expect(screen.queryByText('демо: FSP001 / test')).not.toBeInTheDocument()
  })

  it('без демо-режима не предлагает аккаунт жюри', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: false } })
    renderLogin()
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Взять свободный аккаунт жюри' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Войти как жюри' })).not.toBeInTheDocument()
    expect(screen.queryByText('Стенд сбрасывается каждую ночь')).not.toBeInTheDocument()
  })
})

describe('safeNextPath', () => {
  it('принимает относительный путь и отвергает open redirect', async () => {
    const { safeNextPath } = await import('../LoginPage')
    expect(safeNextPath('/employer/search')).toBe('/employer/search')
    expect(safeNextPath('//evil.com')).toBeNull()
    expect(safeNextPath('https://evil.com')).toBeNull()
    expect(safeNextPath('/login?role=employer')).toBe('/login?role=employer')
  })
})
