import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ResumesCard from '../ResumesCard'

const { listResumes, addResume, deleteResume } = vi.hoisted(() => ({
  listResumes: vi.fn(), addResume: vi.fn(), deleteResume: vi.fn(),
}))

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, listResumes, addResume, deleteResume }
})

const primary = { id: null, specialization: 'backend', label: 'Backend-разработка', grade: 'middle', grade_source: 'assessed', primary: true }
const mobile = { id: 'r1', specialization: 'mobile', label: 'Мобильная разработка', grade: 'junior', stack: ['Kotlin'], summary: 'Два приложения' }

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><ResumesCard /></QueryClientProvider>)
}

describe('резюме кандидата', () => {
  it('добавляет резюме по другой специализации и не предлагает занятые', async () => {
    listResumes.mockResolvedValue({ data: { primary, extras: [], extra_max: 2 } })
    addResume.mockResolvedValue({ data: { primary, extras: [mobile], extra_max: 2 } })
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Добавить резюме' }))
    const spec = screen.getByLabelText('Специализация')
    expect(spec.querySelector('option[value="backend"]')).toBeNull()
    await userEvent.selectOptions(spec, 'mobile')
    await userEvent.type(screen.getByLabelText('Стек через запятую'), 'Kotlin, Compose')
    await userEvent.type(screen.getByLabelText('Коротко об опыте'), 'Два приложения')
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить резюме' }))
    await waitFor(() => expect(addResume).toHaveBeenCalledWith(
      { specialization: 'mobile', grade: 'junior', stack: ['Kotlin', 'Compose'], summary: 'Два приложения' }))
    expect(await screen.findByTestId('resume-extra')).toHaveTextContent('Мобильная разработка')
  })

  it('при трёх резюме больше не добавляет, удаляет лишнее', async () => {
    const qa = { ...mobile, id: 'r2', specialization: 'qa', label: 'Тестирование' }
    listResumes.mockResolvedValue({ data: { primary, extras: [mobile, qa], extra_max: 2 } })
    deleteResume.mockResolvedValue({ data: { primary, extras: [qa], extra_max: 2 } })
    show()
    expect(await screen.findAllByTestId('resume-extra')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Добавить резюме' })).not.toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('button', { name: 'Удалить' })[0])
    await waitFor(() => expect(deleteResume).toHaveBeenCalledWith('r1'))
    await waitFor(() => expect(screen.getAllByTestId('resume-extra')).toHaveLength(1))
  })
})
