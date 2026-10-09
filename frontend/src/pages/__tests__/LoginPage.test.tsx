import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '../LoginPage'

const { publicDemo, publicJuryFree } = vi.hoisted(() => ({ publicDemo: vi.fn(), publicJuryFree: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, publicJuryFree, loginParticipant: vi.fn(), loginEmployer: vi.fn() }
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

  it('напоминает, что стенд сбрасывается каждую ночь', async () => {
    renderLogin()
    expect(await screen.findByText('Стенд сбрасывается каждую ночь')).toBeInTheDocument()
  })

  it('без демо-режима не предлагает аккаунт жюри', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: false } })
    renderLogin()
    expect(await screen.findByRole('button', { name: 'Войти' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Взять свободный аккаунт жюри' })).not.toBeInTheDocument()
    expect(screen.queryByText('Стенд сбрасывается каждую ночь')).not.toBeInTheDocument()
  })
})
