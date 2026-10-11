import { describe, expect, it } from 'vitest'
import { GRADE_RU, JOB_SEARCH_BADGE, JOB_SEARCH_RU, SESSION_STATUS_RU, gradeRu, roleRu, skillRu, industryRu } from '../labels'

describe('подписи грейда и статусов', () => {
  it('переводит грейд на русский', () => {
    expect(gradeRu('middle')).toBe('мидл')
    expect(gradeRu('intern')).toBe(GRADE_RU.intern)
  })

  it('пустой грейд не подставляет чужое слово', () => {
    expect(gradeRu(null)).toBe('')
    expect(gradeRu(undefined)).toBe('')
  })

  it('неизвестный код грейда остаётся как есть', () => {
    expect(gradeRu('principal')).toBe('principal')
  })

  it('статусы сессии и поиска работы читаются по-русски', () => {
    expect(SESSION_STATUS_RU.completed).toBe('завершён')
    expect(SESSION_STATUS_RU.abandoned).toBe('прерван')
    expect(JOB_SEARCH_RU.not_looking).toBe('Не ищу')
    expect(JOB_SEARCH_RU.active).toBe('Активно ищу')
  })

  it('роль и плашка поиска не путают кандидата с работодателем', () => {
    expect(roleRu('qa')).toBe('Тестирование')
    expect(roleRu(null)).toBe('роль не определена')
    expect(JOB_SEARCH_BADGE.JOB_SEARCH_OPEN).toBe('Открыт к предложениям')
  })

  it('skillRu и industryRu', () => {
    expect(skillRu('Algorithms')).toBe('Алгоритмы')
    expect(skillRu('Python')).toBe('Python')
    expect(industryRu('fintech')).toBe('Финансы и финтех')
    expect(industryRu('Свой текст')).toBe('Свой текст')
  })
})
