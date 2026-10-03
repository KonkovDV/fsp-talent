export const ROLE_RU: Record<string, string> = {
  backend: 'бэкенд', frontend: 'фронтенд', fullstack: 'фулстек', ml: 'ML',
  devops: 'DevOps', security: 'ИБ', embedded: 'embedded', mobile: 'мобильная разработка',
}

export const DISC_RU: Record<string, string> = {
  algorithmic: 'Алгоритмика', product: 'Продукт', security: 'Безопасность', bas: 'БАС', robotics: 'Робототехника',
}

export function roleRu(role?: string | null): string {
  if (!role) return 'роль не определена'
  return ROLE_RU[role] ?? role
}
