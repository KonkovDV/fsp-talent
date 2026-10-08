import { mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Browser, type Page } from '@playwright/test'

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
  { name: 'тест', path: '/candidate/assessment', heading: /Тест на грейд/, account: 'candidate' },
  { name: 'приглашения кандидата', path: '/candidate/offers', heading: /^Приглашения$/, account: 'candidate' },
  { name: 'кабинет работодателя', path: '/employer', heading: /Кабинет работодателя/, account: 'employer' },
  { name: 'поиск', path: '/employer/search', heading: /Поиск кандидатов/, account: 'employer' },
]

const authDir = join(tmpdir(), 'fsp-a11y-auth')
const authFile = {
  candidate: join(authDir, 'candidate.json'),
  employer: join(authDir, 'employer.json'),
}

async function signIn(browser: Browser, email: string, role: 'candidate' | 'employer') {
  const page = await browser.newPage()
  const query = role === 'employer' ? '?role=employer' : ''
  await page.goto(`${BASE}/login${query}`)
  await page.locator('#username').fill(email)
  await page.locator('#password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(role === 'employer' ? /\/employer/ : /\/candidate/)
  await page.context().storageState({ path: authFile[role] })
  await page.context().close()
}

async function settle(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready
    const pending = document.getAnimations().filter(animation => {
      const iterations = animation.effect?.getComputedTiming().iterations
      return iterations !== Infinity
    })
    await Promise.all(pending.map(animation => animation.finished.catch(() => undefined)))
  })
}

test.beforeAll(async ({ browser }) => {
  mkdirSync(authDir, { recursive: true })
  await signIn(browser, 'fsp001@demo.talent', 'candidate')
  await signIn(browser, 'hr@sibcode.demo', 'employer')
})

for (const theme of ['light', 'dark'] as const) {
  for (const width of [1440, 390]) {
    test.describe(`${theme}, ${width}px`, () => {
      for (const screen of screens) {
        test(screen.name, async ({ browser }) => {
          const context = await browser.newContext({
            viewport: { width, height: width === 390 ? 844 : 900 },
            reducedMotion: 'reduce',
            storageState: screen.account ? authFile[screen.account] : undefined,
            locale: 'ru-RU',
          })
          const page = await context.newPage()
          await page.addInitScript(value => localStorage.setItem('fsp-theme', value), theme)
          await page.goto(`${BASE}${screen.path}`)
          await expect(page.getByRole('heading', { name: screen.heading }).first()).toBeVisible()
          await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
          await settle(page)
          await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
          const fits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
          expect(fits, 'страница шире окна').toBe(true)
          const result = await new AxeBuilder({ page })
            .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
            .analyze()
          const blocked = result.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')
          expect(blocked.map(item => ({
            id: item.id,
            impact: item.impact,
            nodes: item.nodes.slice(0, 3).map(node => node.target.join(' ')),
          }))).toEqual([])
          await context.close()
        })
      }
    })
  }
}
