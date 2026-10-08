import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AccountSecurity from '../AccountSecurity'

const { changePassword } = vi.hoisted(() => ({ changePassword: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, changePassword, downloadMyData: vi.fn() }
})

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AccountSecurity />
    </QueryClientProvider>,
  )
}

async function fill(current: string, next: string, again = next) {
  await userEvent.type(screen.getByLabelText('Текущий пароль'), current)
  await userEvent.type(screen.getByLabelText('Новый пароль'), next)
  await userEvent.type(screen.getByLabelText('Новый пароль ещё раз'), again)
}

beforeEach(() => {
  changePassword.mockReset()
})

describe('пароль аккаунта', () => {
  it('демо-аккаунт получает нейтральное сообщение, не ошибку', async () => {
    changePassword.mockRejectedValue({
      response: { data: { error: { code: 'demo_protected', message: 'Демо-аккаунт: пароль и удаление закрыты, чтобы жюри могло войти' } } },
    })
    renderCard()
    await fill('old-pass', 'new-pass-1')
    await userEvent.click(screen.getByRole('button', { name: 'Сменить пароль' }))
    const note = await screen.findByRole('status')
    expect(note).toHaveTextContent('Демо-аккаунт: пароль и удаление закрыты')
    expect(note.className).not.toContain('field-error')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('обычный отказ остаётся ошибкой', async () => {
    changePassword.mockRejectedValue({
      response: { data: { error: { code: 'wrong_password', message: 'Текущий пароль не подошёл' } } },
    })
    renderCard()
    await fill('old-pass', 'new-pass-1')
    await userEvent.click(screen.getByRole('button', { name: 'Сменить пароль' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Текущий пароль не подошёл')
  })

  it('не сохраняет пароль, пока повтор не совпал', async () => {
    renderCard()
    await fill('old-pass', 'new-pass-1', 'other-pass')
    expect(screen.getByRole('alert')).toHaveTextContent('Пароли не совпадают')
    expect(screen.getByRole('button', { name: 'Сменить пароль' })).toBeDisabled()
    expect(changePassword).not.toHaveBeenCalled()
  })
})
