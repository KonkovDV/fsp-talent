import { mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test, type Browser } from '@playwright/test'

// WCAG 2.2 SC 1.4.10 Reflow: content at 320 CSS px without horizontal scrolling. Same screens as a11y.spec.ts.
const PASSWORD = 'demo12345'
const BASE = process.env.E2E_BASE_URL || 'http://localhost'

const screens: { name: string; path: string; heading: RegExp; account?: 'candidate' | 'employer' }[] = [
  { name: 'главная', path: '/', heading: /Приглашайте разработчиков/ },
  { name: 'вход', path: '/login', heading: /^Вход$/ },
  { name: 'регистрация', path: '/register', heading: /^Регистрация$/ },
  { name: 'методика', path: '/method', heading: /Как устроен тест/ },
  { name: 'жюри', path: '/jury', heading: /Режим жюри/ },
  { name: 'документы', path: '/legal', heading: /Документы и согласия/ },
  { name: 'кабинет кандидата', path: '/candidate', heading: /Здравствуйте|Кабинет/, account: 'candidate' },
  { name: 'профиль кандидата', path: '/candidate/profile', heading: /.+/, account: 'candidate' },
  { name: 'тест', path: '/candidate/assessment', heading: /Тест на грейд/, account: 'candidate' },
  { name: 'приглашения кандидата', path: '/candidate/offers', heading: /^Приглашения$/, account: 'candidate' },
  { name: 'кабинет работодателя', path: '/employer', heading: /Кабинет работодателя/, account: 'employer' },
  { name: 'потребности', path: '/employer/needs', heading: /^Потребности$/, account: 'employer' },
  { name: 'поиск', path: '/employer/search', heading: /Поиск кандидатов/, account: 'employer' },
]

const authDir = join(tmpdir(), 'fsp-narrow-auth')
const authFile = { candidate: join(authDir, 'candidate.json'), employer: join(authDir, 'employer.json') }

async function signIn(browser: Browser, email: string, role: 'candidate' | 'employer') {
  const page = await browser.newPage()
  await page.goto(`${BASE}/login${role === 'employer' ? '?role=employer' : ''}`)
  await page.locator('#username').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(role === 'employer' ? /\/employer/ : /\/candidate/)
  await page.context().storageState({ path: authFile[role] })
  await page.context().close()
}

test.beforeAll(async ({ browser }) => {
  mkdirSync(authDir, { recursive: true })
  await signIn(browser, 'fsp001@demo.talent', 'candidate')
  await signIn(browser, 'hr@sibcode.demo', 'employer')
})

for (const width of [360, 320]) {
  test.describe(`${width}px`, () => {
    for (const screen of screens) {
      test(screen.name, async ({ browser }) => {
        const context = await browser.newContext({
          viewport: { width, height: 740 }, reducedMotion: 'reduce', locale: 'ru-RU',
          storageState: screen.account ? authFile[screen.account] : undefined,
        })
        const page = await context.newPage()
        await page.goto(`${BASE}${screen.path}`)
        await expect(page.getByRole('heading', { name: screen.heading }).first()).toBeVisible()
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
        // Name the widest offenders, so a failure says what to fix.
        const wide = await page.evaluate(() => {
          const limit = window.innerWidth + 1
          if (document.documentElement.scrollWidth <= limit) return []
          return [...document.querySelectorAll<HTMLElement>('body *')]
            .filter(el => el.getBoundingClientRect().right > limit && getComputedStyle(el).position !== 'fixed')
            .filter(el => !el.closest('[class*="overflow-x-auto"], [class*="overflow-auto"], pre, table'))
            .slice(0, 5)
            .map(el => `${el.tagName.toLowerCase()}.${el.className.toString().split(' ').slice(0, 4).join('.')} → ${Math.round(el.getBoundingClientRect().right)}px`)
        })
        expect(wide, 'страница шире окна').toEqual([])
        await context.close()
      })
    }
  })
}
