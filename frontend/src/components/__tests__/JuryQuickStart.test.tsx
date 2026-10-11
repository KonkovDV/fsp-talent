import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import JuryQuickStart from '../JuryQuickStart'

const { publicJuryFree, loginParticipant, startAssessment } = vi.hoisted(() => ({
  publicJuryFree: vi.fn(), loginParticipant: vi.fn(), startAssessment: vi.fn(),
}))
vi.mock('../../api/client', () => ({
  publicJuryFree, loginParticipant, startAssessment,
  apiErrorCode: (e: { code?: string }) => e?.code ?? null,
}))

function renderBlock() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<JuryQuickStart />} />
        <Route path="/candidate/assessment" element={<p>страница теста</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  publicJuryFree.mockReset(); loginParticipant.mockReset(); startAssessment.mockReset()
  loginParticipant.mockResolvedValue({ data: { access_token: 't' } })
})

describe('вход жюри с главной', () => {
  it('одной кнопкой берёт свободный jury*, запускает экспресс и открывает тест', async () => {
    publicJuryFree.mockResolvedValue({ data: { email: 'jury3@demo.talent' } })
    startAssessment.mockResolvedValue({ data: {} })
    renderBlock()
    await userEvent.click(screen.getByRole('button', { name: 'Пройти экспресс-тест за 5 минут' }))
    expect(await screen.findByText('страница теста')).toBeInTheDocument()
    expect(loginParticipant).toHaveBeenCalledWith('jury3@demo.talent', 'demo12345')
    expect(startAssessment).toHaveBeenCalledWith(expect.objectContaining({ mode: 'express', specialization: 'backend' }))
  })

  it('незавершённый тест этого аккаунта открывается как есть', async () => {
    publicJuryFree.mockResolvedValue({ data: { email: 'jury7@demo.talent' } })
    startAssessment.mockRejectedValue({ code: 'conflict' })
    renderBlock()
    await userEvent.click(screen.getByRole('button', { name: 'Пройти экспресс-тест за 5 минут' }))
    expect(await screen.findByText('страница теста')).toBeInTheDocument()
  })

  it('без свободного аккаунта — понятное сообщение и ссылка на страницу жюри', async () => {
    publicJuryFree.mockRejectedValue(new Error('offline'))
    renderBlock()
    await userEvent.click(screen.getByRole('button', { name: 'Пройти экспресс-тест за 5 минут' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Свободного аккаунта жюри сейчас нет')
    expect(screen.getByRole('link', { name: 'Открыть страницу жюри' })).toHaveAttribute('href', '/jury')
    expect(loginParticipant).not.toHaveBeenCalled()
  })
})
