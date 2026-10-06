import { expect, test, type Page } from '@playwright/test'

const MAIL = process.env.E2E_MAIL_URL || 'http://localhost:8025'
const PASSWORD = 'demo12345'

async function session(page: Page) {
  return page.evaluate(() => {
    const raw = localStorage.getItem('fsp-auth')
    return raw ? (JSON.parse(raw).state as { token: string; userId: string }) : null
  })
}

async function confirmationCode(email: string) {
  for (let i = 0; i < 20; i++) {
    const list = await fetch(`${MAIL}/api/v1/search?query=${encodeURIComponent(email)}`)
    if (list.ok) {
      const data = await list.json() as { messages?: { ID: string }[] }
      const id = data.messages?.[0]?.ID
      if (id) {
        const letter = await fetch(`${MAIL}/api/v1/message/${id}`)
        const body = await letter.json() as { Text?: string; HTML?: string }
        const found = `${body.Text || ''} ${body.HTML || ''}`.match(/\b(\d{6})\b/)
        if (found) return found[1]
      }
    }
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  throw new Error(`Письмо с кодом для ${email} не пришло в Mailpit`)
}

async function answerOne(page: Page, step: number) {
  await expect(page.getByText(`Задание ${step}.`)).toBeVisible()
  const item = page.getByTestId('assessment-item')
  const typed = item.locator('#typed-answer')
  if (await typed.isVisible()) await typed.fill(String(step))
  else await item.getByRole('radio').first().click()
  await item.getByRole('button', { name: 'Ответить' }).click()
}

test('кабинеты читаются на узком экране в тёмной теме', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/login')
  await page.getByRole('button', { name: 'Тёмная тема' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.locator('#username').fill('fsp001@demo.talent')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/candidate/)
  await page.goto('/candidate/assessment')
  await expect(page.getByRole('button', { name: /Пробный тест/ })).toBeVisible()
  await page.goto('/candidate/offers')
  await expect(page.getByLabel('Причина отказа').first()).toBeVisible()
  const candidateFits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
  expect(candidateFits).toBeTruthy()

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)
  await page.goto('/employer/needs')
  await expect(page.getByRole('heading', { name: 'Потребности' })).toBeVisible()
  await page.goto('/employer/offers')
  await expect(page.getByRole('heading', { name: 'Приглашения' })).toBeVisible()
  const employerFits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
  expect(employerFits).toBeTruthy()
})

test('кандидат проходит регистрацию и пробный тест, работодатель открывает контакты только после согласия', async ({ page, request }) => {
  const email = `e2e-${Date.now()}@demo.talent`
  const name = 'Ева Проверка'

  await page.goto('/register')
  await page.locator('#display_name').fill(name)
  await page.locator('#email').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('checkbox', { name: /Мне исполнилось 18 лет/ }).check()
  for (const box of await page.getByTestId(/consent-/).all()) await box.check()
  await page.getByRole('button', { name: 'Получить код на email' }).click()
  await expect(page.getByRole('heading', { name: 'Подтвердите email' })).toBeVisible()

  const code = await confirmationCode(email)
  await page.getByLabel('Код из письма').fill(code)
  await page.getByRole('button', { name: 'Подтвердить' }).click()
  await expect(page).toHaveURL(/\/candidate/)

  await page.getByLabel('Специализация').selectOption('backend')
  await page.getByLabel('Предметная область').selectOption({ index: 1 })
  await page.getByLabel('Ожидания по зарплате, от').fill('200000')
  await page.getByRole('button', { name: 'Сохранить опрос' }).click()
  await expect(page.getByRole('region', { name: 'Категория' })).toContainText('Backend')

  await page.goto('/candidate/assessment')
  await page.getByRole('button', { name: /Пробный тест/ }).click()
  for (let step = 1; step <= 6; step++) await answerOne(page, step)
  await expect(page.getByRole('status')).toContainText('не подтверждается')

  const candidate = await session(page)
  expect(candidate?.userId).toBeTruthy()

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)

  await page.goto('/employer/needs')
  const toShortlist = page.getByRole('button', { name: 'В шорт-лист', exact: true }).first()
  await expect(toShortlist).toBeVisible()
  await toShortlist.click()
  await expect(page.getByRole('button', { name: 'В шорт-листе', exact: true }).first()).toBeVisible()

  const employer = await session(page)
  const created = await request.post('/api/v1/offers/', {
    headers: { Authorization: `Bearer ${employer?.token}` },
    data: {
      candidate_id: candidate?.userId,
      role: 'Backend-разработчик',
      salary_from_gross: 150000,
      salary_to_gross: 180000,
      work_format: 'remote',
      contact_method: 'email',
    },
  })
  expect(created.ok(), await created.text()).toBeTruthy()
  const offer = await created.json() as { id: string }
  const hidden = await request.get(`/api/v1/offers/${offer.id}/contacts`, {
    headers: { Authorization: `Bearer ${employer?.token}` },
  })
  expect(hidden.status()).toBe(403)

  await page.goto('/employer/offers')
  await expect(page.getByText(email)).toHaveCount(0)

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login')
  await page.locator('#username').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/candidate/)
  await page.goto('/candidate/offers')
  await page.getByRole('button', { name: 'Принять и открыть контакты' }).click()
  await expect(page.getByText('принято').first()).toBeVisible()

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)
  const opened = await request.get(`/api/v1/offers/${offer.id}/contacts`, {
    headers: { Authorization: `Bearer ${(await session(page))?.token}` },
  })
  expect(opened.ok()).toBeTruthy()
  const contacts = await opened.json() as { email: string; display_name: string }
  expect(contacts.email).toBe(email)
  expect(contacts.display_name).toBe(name)
  await page.goto('/employer/offers')
  const row = page.locator(`tr[data-offer-id="${offer.id}"]`)
  await row.getByRole('button', { name: 'Открыть контакты' }).click()
  await expect(row.getByText(email)).toBeVisible()
})
