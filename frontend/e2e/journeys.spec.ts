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
  await page.getByLabel('Грейд', { exact: true }).selectOption('middle')
  await page.getByLabel('Ожидания по зарплате, от').fill('200000')
  await page.getByRole('button', { name: 'Сохранить опрос' }).click()
  await expect(page.getByRole('region', { name: 'Категория' })).toContainText('Backend')

  await page.goto('/candidate/assessment')
  await page.getByRole('button', { name: /Пробный тест/ }).click()
  // The trial length comes from the stand (blueprint.express_items); answer until the neutral verdict shows.
  const verdict = page.getByTestId('trial-verdict')
  for (let step = 1; step <= 20; step++) {
    await expect(page.getByText(`Задание ${step}.`).or(verdict)).toBeVisible()
    if (await verdict.isVisible()) break
    await answerOne(page, step)
  }
  await expect(verdict).toContainText('Вероятность уровня')
  await expect(page.getByRole('status').first()).toContainText('не подтверждается')

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

test('до принятия контактов нет ни в карточке, ни в ответе API', async ({ page }) => {
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)
  await page.goto('/employer/search')
  const card = page.getByTestId('candidate-card').first()
  await expect(card).toBeVisible()
  await expect(card).not.toContainText('@')
  const token = (await session(page))?.token
  const found = await page.request.get('/api/v1/search/candidates?limit=20', {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(found.ok(), await found.text()).toBeTruthy()
  const body = await found.json() as { items: Record<string, unknown>[] }
  expect(body.items.length).toBeGreaterThan(0)
  for (const item of body.items) {
    expect(item.email).toBeUndefined()
    expect(item.display_name).toBeUndefined()
    expect(item.phone).toBeUndefined()
    expect(item.telegram).toBeUndefined()
  }
})

async function loginCandidate(page: Page, email: string) {
  await page.goto('/login')
  await page.locator('#username').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/candidate/)
}

async function passTrial(page: Page) {
  await page.goto('/candidate/assessment')
  const verdict = page.getByTestId('trial-verdict')
  const again = page.getByRole('button', { name: 'К тестам' })
  const survey = page.getByLabel('Специализация')
  const trial = page.getByRole('button', { name: /Пробный тест/ })
  const item = page.getByText(/Задание \d+\./)
  await expect(trial.or(survey).or(again).or(item)).toBeVisible()
  if (await again.isVisible()) {
    await again.click()
    await expect(verdict).toBeHidden()
  }
  if (await survey.isVisible() && !(await trial.isVisible())) {
    await survey.selectOption('backend')
    await page.getByLabel('Грейд', { exact: true }).selectOption('junior')
    await page.getByRole('button', { name: 'Сохранить опрос' }).click()
  }
  const running = page.getByTestId('assessment-item')
  if (!(await running.isVisible())) {
    await expect(trial).toBeEnabled()
    await trial.click()
    const alert = page.getByRole('alert')
    await expect(running.or(alert)).toBeVisible()
    if (await alert.isVisible() && !(await running.isVisible())) throw new Error(await alert.innerText())
  }
  await expect(page.getByText('Это пробный проход')).toBeVisible()
  for (let step = 1; step <= 20; step++) {
    await expect(page.getByText(`Задание ${step}.`).or(verdict)).toBeVisible()
    if (await verdict.isVisible()) break
    await answerOne(page, step)
  }
  await expect(verdict).toBeVisible()
  await expect(page.getByText('не подтверждается').first()).toBeVisible()
}

async function registerCandidate(page: Page, email: string, name: string) {
  await page.goto('/register')
  await page.locator('#display_name').fill(name)
  await page.locator('#email').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('checkbox', { name: /Мне исполнилось 18 лет/ }).check()
  for (const box of await page.getByTestId(/consent-/).all()) await box.check()
  await page.getByRole('button', { name: 'Получить код на email' }).click()
  await expect(page.getByRole('heading', { name: 'Подтвердите email' })).toBeVisible()
  await page.getByLabel('Код из письма').fill(await confirmationCode(email))
  await page.getByRole('button', { name: 'Подтвердить' }).click()
  await expect(page).toHaveURL(/\/candidate/)
  await page.getByLabel('Специализация').selectOption('backend')
  await page.getByLabel('Грейд', { exact: true }).selectOption('junior')
  await page.getByRole('button', { name: 'Сохранить опрос' }).click()
  await expect(page.getByRole('region', { name: 'Категория' })).toContainText('Backend')
}

test('кандидат откликается на вакансию, работодатель видит контакты и меняет статус', async ({ page }) => {
  const email = `e2e-apply-${Date.now()}@demo.talent`
  const name = 'Пётр Отклик'
  const vacancy = 'Стажёр backend'
  await registerCandidate(page, email, name)

  await page.goto('/candidate/vacancies')
  const card = page.locator('li.card', { has: page.getByRole('heading', { name: vacancy }) })
  await card.getByRole('button', { name: 'Откликнуться' }).click()
  await expect(card.getByRole('button', { name: 'Отклик отправлен' })).toBeVisible()
  await page.reload()
  const mine = page.locator('section', { has: page.getByRole('heading', { name: 'Мои отклики' }) })
  await expect(mine).toContainText('отправлен')

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)
  await page.goto('/employer/vacancies')
  const row = page.getByRole('row', { name: new RegExp(vacancy) }).first()
  await row.getByRole('button', { name: 'Показать контакты' }).click()
  await expect(row).toContainText(email)
  await expect(row).toContainText(name)
  await row.getByLabel(`Статус отклика ${vacancy}`).selectOption({ label: 'смотрим' })

  await page.getByRole('button', { name: 'Выйти' }).click()
  await loginCandidate(page, email)
  await page.goto('/candidate/vacancies')
  await expect(page.locator('section', { has: page.getByRole('heading', { name: 'Мои отклики' }) })).toContainText('смотрят')
})

test('вход через ФСП ID показывает результаты, а карточку работодателю — нет', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('fsp-signin').click()
  await expect(page).toHaveURL(/\/fsp-id\/authorize/)
  await page.getByLabel('ФСП ID').fill('FSP2077')
  await page.getByLabel('Пароль').fill('test')
  await page.getByRole('button', { name: 'Войти и разрешить' }).click()
  await expect(page).toHaveURL(/\/auth\/fsp-callback|\/candidate/)
  const create = page.getByRole('button', { name: 'Создать аккаунт и войти' })
  const home = page.getByRole('link', { name: 'Результаты ФСП' })
  await expect(create.or(home)).toBeVisible()
  if (await create.isVisible()) {
    for (const box of await page.getByTestId(/consent-/).all()) await box.check()
    await create.click()
  }
  await expect(page).toHaveURL(/\/candidate/)
  const candidateId = (await session(page))?.userId
  expect(candidateId).toBeTruthy()

  await page.goto('/candidate/results')
  await expect(page.getByRole('heading', { name: 'Результаты ФСП' })).toBeVisible()
  await expect(page.getByText(/робототехника/)).toBeVisible()

  await page.goto('/candidate')
  await expect(page.getByText('работодатели увидят карточку только после согласия представителя')).toBeVisible()
  const survey = page.getByLabel('Специализация')
  if (await survey.isVisible()) {
    await survey.selectOption('embedded')
    await page.getByLabel('Грейд', { exact: true }).selectOption('junior')
    await page.getByRole('button', { name: 'Сохранить опрос' }).click()
    await expect(page.getByRole('region', { name: 'Категория' })).toBeVisible()
  }
  await expect(page.getByText('работодатели увидят карточку только после согласия представителя')).toBeVisible()

  await page.getByRole('button', { name: 'Выйти' }).click()
  await page.goto('/login?role=employer')
  await page.locator('#username').fill('hr@sibcode.demo')
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/employer/)
  const token = (await session(page))?.token
  const found = await page.request.get('/api/v1/search/candidates?discipline=robotics&has_fsp=true&limit=50', {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(found.ok(), await found.text()).toBeTruthy()
  const body = await found.json() as { total: number; items: { candidate_id: string }[] }
  expect(body.items.map(item => item.candidate_id)).not.toContain(candidateId)
})

test('член жюри jury2 проходит пробный тест сразу после jury1', async ({ page }) => {
  await loginCandidate(page, 'jury1@demo.talent')
  await passTrial(page)
  await page.getByRole('button', { name: 'Выйти' }).click()
  await loginCandidate(page, 'jury2@demo.talent')
  await passTrial(page)
})
