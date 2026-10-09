import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ForgotPasswordPage from '../ForgotPasswordPage'

const { publicDemo } = vi.hoisted(() => ({ publicDemo: vi.fn() }))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, publicDemo, forgotPassword: vi.fn(), resetPassword: vi.fn() }
})

beforeEach(() => {
  publicDemo.mockResolvedValue({ data: { demo_mode: false, mail_console: false } })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/forgot?role=participant']}>
      <ForgotPasswordPage />
    </MemoryRouter>,
  )
}

describe('сброс пароля', () => {
  it('на демо-стенде без почты не показывает код', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: true, mail_console: true } })
    renderPage()
    const note = 'На демо-стенде письма не отправляются, используйте демо-аккаунты.'
    expect(await screen.findAllByText(note)).not.toHaveLength(0)
    expect(screen.queryByLabelText('Код из письма')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Прислать код' })).not.toBeInTheDocument()
  })

  it('когда письма уходят, просит код как обычно', async () => {
    publicDemo.mockResolvedValue({ data: { demo_mode: true, mail_console: false } })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Прислать код' })).toBeInTheDocument()
    expect(screen.queryByText('На демо-стенде письма не отправляются, используйте демо-аккаунты.')).not.toBeInTheDocument()
  })
})
