import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '../LoginPage'

const { publicDemo } = vi.hoisted(() => ({ publicDemo: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, loginParticipant: vi.fn(), loginEmployer: vi.fn() }
})

beforeEach(() => {
  publicDemo.mockResolvedValue({ data: { demo_mode: true } })
})

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

describe('вход', () => {
  it('кладёт в форму свободный аккаунт жюри', async () => {
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
