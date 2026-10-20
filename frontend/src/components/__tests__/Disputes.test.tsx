import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import DisputeBox from '../DisputeBox'
import MyDisputes from '../MyDisputes'
import DisputeDesk from '../../pages/employer/DisputeDesk'

const m = vi.hoisted(() => ({
  disputeGrade: vi.fn(), myDisputes: vi.fn(), deskDisputes: vi.fn(), deskDispute: vi.fn(), decideDispute: vi.fn(),
}))
vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, ...m }
})

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

const attempt = {
  session_id: 's1', specialization: 'backend', target_grade: 'middle', status: 'completed', outcome: 'not_passed',
  items_count: 12, p_pass: 0.41, theta_se: 0.3, stop_reason: 'decided', started_at: '2026-10-20T10:00:00Z',
  completed_at: '2026-10-20T10:20:00Z', duration_s: 1200, integrity_level: 'none', integrity_signals: [],
  person_fit_review: false, voidable: true, voided: false,
}
const open = {
  id: 'd1', session_id: 's1', status: 'open', status_label: 'на рассмотрении', reason: 'задание не открылось',
  decision_note: null, created_at: '2026-10-20T10:30:00Z', due_at: '2026-11-19T10:30:00Z', decided_at: null,
  overdue: false, attempt,
}

describe('обращение по тесту', () => {
  it('кандидат отправляет причину и видит срок ответа', async () => {
    m.disputeGrade.mockResolvedValue({ data: { text: 'Грейд этой кнопкой не меняется.', status: 'open', due_at: '2026-11-19T10:30:00Z' } })
    const user = userEvent.setup()
    wrap(<DisputeBox sessionId="s1" />)
    await user.type(screen.getByLabelText('Что пошло не так (необязательно)'), 'задание не открылось')
    await user.click(screen.getByRole('button', { name: 'Оспорить результат' }))
    expect(m.disputeGrade).toHaveBeenCalledWith('s1', 'задание не открылось')
    expect(await screen.findByRole('status')).toHaveTextContent('Грейд этой кнопкой не меняется')
    expect(screen.getByRole('status')).toHaveTextContent('19.11.2026')
  })

  it('список показывает ответ методиста и последствия аннулирования', async () => {
    m.myDisputes.mockResolvedValue({ data: [{ ...open, status: 'voided', status_label: 'попытка аннулирована', decision_note: 'Сбой таймера подтверждён журналом.' }] })
    wrap(<MyDisputes />)
    expect(await screen.findByText('попытка аннулирована')).toBeInTheDocument()
    expect(screen.getByText(/Сбой таймера подтверждён журналом/)).toBeInTheDocument()
    expect(screen.getByText(/не мешает пересдаче/)).toBeInTheDocument()
  })

  it('методист видит попытку и не может решить без ответа кандидату', async () => {
    m.deskDisputes.mockResolvedValue({ data: [open] })
    m.deskDispute.mockResolvedValue({
      data: {
        ...open,
        items: [{
          seq: 1, family_id: 'py_eval', level: 2, kind: 'code', topic: 'python', stem: 'Что выведет код?',
          code: 'print(6)', language: 'python', given: '7', right: '6', correct: false, timed_out: false,
          excluded: false, time_limit_s: 180, spent_s: 40,
        }],
      },
    })
    m.decideDispute.mockResolvedValue({ data: { ...open, status: 'voided' } })
    const user = userEvent.setup()
    wrap(<DisputeDesk />)
    expect(await screen.findByText('Кандидат пишет: задание не открылось')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Открыть попытку' }))
    expect(await screen.findByText('Что выведет код?')).toBeInTheDocument()
    const voidButton = screen.getByRole('button', { name: 'Аннулировать попытку' })
    expect(voidButton).toBeDisabled()
    await user.type(screen.getByLabelText('Ответ кандидату'), 'Сбой таймера подтверждён журналом.')
    await user.click(voidButton)
    expect(m.decideDispute).toHaveBeenCalledWith('d1', 'void', 'Сбой таймера подтверждён журналом.')
  })
})
