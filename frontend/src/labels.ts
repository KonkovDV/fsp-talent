export const ROLE_RU: Record<string, string> = {
  backend: 'Backend', frontend: 'Frontend', fullstack: 'Fullstack', ml: 'ML и данные',
  devops: 'DevOps', security: 'Информационная безопасность', embedded: 'Встраиваемые системы', mobile: 'Мобильная разработка',
}

export const DISC_RU: Record<string, string> = {
  algorithmic: 'Алгоритмическое', product: 'Продуктовое', security: 'Системы ИБ', bas: 'БАС', robotics: 'Робототехника',
  ai: 'Системы ИИ',
}

export const GRADES = ['intern', 'junior', 'middle', 'senior', 'lead'] as const

export const GRADE_RU: Record<string, string> = {
  intern: 'стажёр', junior: 'junior', middle: 'middle', senior: 'senior', lead: 'lead',
}

export function gradeRu(grade?: string | null): string {
  if (!grade) return ''
  return GRADE_RU[grade] ?? grade
}

export function roleRu(role?: string | null): string {
  if (!role) return 'роль не определена'
  return ROLE_RU[role] ?? role
}
