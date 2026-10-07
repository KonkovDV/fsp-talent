export const ROLE_RU: Record<string, string> = {
  backend: 'Backend', frontend: 'Frontend', fullstack: 'Fullstack', ml: 'ML и данные',
  devops: 'DevOps', security: 'Информационная безопасность', embedded: 'Встраиваемые системы', mobile: 'Мобильная разработка',
  qa: 'Тестирование', analyst: 'Аналитика', data: 'Инженерия данных',
}

export const DISC_RU: Record<string, string> = {
  algorithmic: 'Алгоритмическое', product: 'Продуктовое', security: 'Системы ИБ', bas: 'БАС', robotics: 'Робототехника',
  ai: 'Системы ИИ',
}

export const GRADES = ['intern', 'junior', 'middle', 'senior', 'lead'] as const

export const GRADE_RU: Record<string, string> = {
  intern: 'стажёр', junior: 'джуниор', middle: 'мидл', senior: 'сеньор', lead: 'лид',
}

/** Session statuses in the test history. */
export const SESSION_STATUS_RU: Record<string, string> = {
  completed: 'завершён', in_progress: 'идёт', abandoned: 'прерван', expired: 'время вышло',
}

export function gradeRu(grade?: string | null): string {
  if (!grade) return ''
  return GRADE_RU[grade] ?? grade
}

export function roleRu(role?: string | null): string {
  if (!role) return 'роль не определена'
  return ROLE_RU[role] ?? role
}
