export const ROLE_RU: Record<string, string> = {
  backend: 'Backend', frontend: 'Frontend', fullstack: 'Fullstack', ml: 'ML и данные',
  devops: 'DevOps', security: 'Информационная безопасность', embedded: 'Встраиваемые системы', mobile: 'Мобильная разработка',
}

export const DISC_RU: Record<string, string> = {
  algorithmic: 'Алгоритмическое', product: 'Продуктовое', security: 'Системы ИБ', bas: 'БАС', robotics: 'Робототехника',
  ai: 'Системы ИИ',
}

export function roleRu(role?: string | null): string {
  if (!role) return 'роль не определена'
  return ROLE_RU[role] ?? role
}
