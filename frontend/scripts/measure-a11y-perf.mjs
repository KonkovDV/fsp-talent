/**
 * Baseline / after: axe-core + Lighthouse against vite preview (prod build).
 * Usage: node scripts/measure-a11y-perf.mjs [outDir]
 * Env: BASE=http://127.0.0.1:4173
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const lighthouseMod = require('lighthouse')
const lighthouse = lighthouseMod.default || lighthouseMod
// Desktop must use the official desktop config (its throttling), not only formFactor:
// formFactor alone keeps mobile throttling (150 ms RTT, 1.6 Mbps, CPU x4) with desktop scoring curves.
const desktopConfig = lighthouseMod.desktopConfig
const chromeLauncher = require('chrome-launcher')

const BASE = process.env.BASE || 'http://127.0.0.1:4173'
const OUT = process.argv[2] || '/workspace/a11y-out/before'

const pages = [
  { name: 'landing', path: '/', public: true },
  { name: 'login', path: '/login', public: true },
  { name: 'jury', path: '/jury', public: true },
  { name: 'method', path: '/method', public: true },
  { name: 'candidate-dashboard', path: '/candidate', role: 'participant' },
  { name: 'assessment', path: '/candidate/assessment', role: 'participant', mockAssessment: true },
  { name: 'employer-needs', path: '/employer/needs', role: 'employer', mockNeeds: true },
  { name: 'employer-search-cards', path: '/employer/search', role: 'employer' },
]

function authInit(role) {
  return (r) => {
    localStorage.setItem('fsp-theme', 'light')
    localStorage.setItem('fsp-auth', JSON.stringify({
      state: {
        token: null, userRole: r, userId: 'example', needsRenew: false,
        guestUntil: null, example: true,
      },
      version: 0,
    }))
  }
}

async function settle(page) {
  await page.waitForTimeout(400)
  await page.evaluate(async () => {
    await document.fonts.ready.catch(() => {})
  }).catch(() => {})
}

async function runAxe(browser, theme) {
  const rows = []
  for (const screen of pages) {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      locale: 'ru-RU',
      reducedMotion: 'reduce',
    })
    const page = await context.newPage()
    await page.addInitScript(t => localStorage.setItem('fsp-theme', t), theme)
    if (screen.role) await page.addInitScript(authInit(screen.role), screen.role)
    if (screen.mockAssessment) {
      await page.route('**/api/v1/assessment/**', async route => {
        if (route.request().method() !== 'GET') return route.fulfill({ status: 409, body: '{}' })
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            session_id: 's1', status: 'in_progress', specialization: 'backend', target_grade: 'middle',
            expires_at: new Date(Date.now() + 3_600_000).toISOString(),
            progress: { answered: 1, min_items: 8, max_items: 20, p_pass: 0.4, se: 0.4, theta: 0 },
            result: null,
            item: {
              token: 'tok-1', seq: 2, stem: 'Сколько будет 2 + 2?', code: null, language: null,
              answer_mode: 'choice',
              options: [{ index: 0, text: 'четыре' }, { index: 1, text: 'пять' }],
              topic_label: 'Арифметика', family_title: 'Сумма', kind: 'code', time_limit_s: 75,
              served_at: new Date().toISOString(),
            },
          }),
        })
      })
    }
    if (screen.mockNeeds) {
      const need = {
        id: '00000000-0000-4000-8000-0000000000b1', title: 'Backend, мидл', version: 1, shortlist_count: 1,
        params: { role: 'backend', grade: 'middle', skills: ['Python'], nice_to_have: [], industry: null, work_goal: null, has_fsp: null },
      }
      await page.route('**/api/v1/needs**', async route => {
        const u = route.request().url()
        const method = route.request().method()
        if (method !== 'GET') return route.fulfill({ status: 409, body: '{}' })
        if (u.includes('/matches')) {
          return route.fulfill({
            status: 200, contentType: 'application/json',
            body: JSON.stringify({
              items: [{
                candidate_id: '00000000-0000-4000-8000-0000000000a1',
                role: 'backend', grade: 'middle', grade_source: 'assessed',
                stack: ['Python'], matched_skills: ['Python'], missing_skills: [],
                region: 'Новосибирск', experience_years: 3, disciplines: [],
                match: { score: 0.74, plus: ['Грейд'], minus: [], info: [], factors: [
                  { key: 'skills', label: 'Навыки', value: 0.8 },
                  { key: 'grade', label: 'Грейд', value: 1 },
                ], reply: { p: 0.7, label: 'высокая' }, basis: 'evidence' },
                why: ['Грейд middle'],
              }],
              total: 1, base_total: 10, hidden_count: 0,
            }),
          })
        }
        if (u.includes('/shortlist')) {
          return route.fulfill({ status: 200, contentType: 'application/json',
            body: JSON.stringify({ items: [], funnel: { shortlisted: 0, invited: 0, rejected: 0 } }) })
        }
        if (/\/needs\/[0-9a-f-]+$/.test(u.split('?')[0])) {
          return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...need, versions: [] }) })
        }
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([need]) })
      })
    }
    try {
      await page.goto(`${BASE}${screen.path}`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
      await settle(page)
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
      const byImpact = { critical: 0, serious: 0, moderate: 0, minor: 0 }
      for (const v of result.violations) {
        byImpact[v.impact || 'minor'] = (byImpact[v.impact || 'minor'] || 0) + 1
      }
      rows.push({
        page: screen.name,
        theme,
        path: screen.path,
        violations: result.violations.length,
        byImpact,
        details: result.violations.map(v => ({
          id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
          targets: v.nodes.slice(0, 4).map(n => n.target.join(' ')),
          failureSummary: v.nodes[0]?.failureSummary?.slice(0, 200),
        })),
      })
      console.log(`axe ${theme} ${screen.name}: ${result.violations.length} (crit=${byImpact.critical} ser=${byImpact.serious} mod=${byImpact.moderate} min=${byImpact.minor})`)
    } catch (e) {
      rows.push({ page: screen.name, theme, path: screen.path, error: String(e) })
      console.error(`axe FAIL ${theme} ${screen.name}`, e.message || e)
    }
    await context.close()
  }
  return rows
}

async function runLighthouse() {
  const chrome = await chromeLauncher.launch({
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'],
    chromePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
  })
  const reports = []
  const targets = pages.filter(p => p.public || p.name === 'candidate-dashboard' || p.name === 'employer-needs' || p.name === 'employer-search-cards' || p.name === 'assessment')
  for (const formFactor of ['mobile', 'desktop']) {
    for (const screen of targets) {
      // Fresh chrome tab via LH; for auth pages use only public for LH reliability
      if (!screen.public) continue
      try {
        const flags = {
          port: chrome.port,
          output: 'json',
          logLevel: 'error',
          onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
          ...(formFactor === 'mobile'
            ? { formFactor, screenEmulation: { mobile: true, width: 390, height: 844, deviceScaleFactor: 2, disabled: false } }
            : {}),
        }
        const result = await lighthouse(`${BASE}${screen.path}`, flags, formFactor === 'desktop' ? desktopConfig : undefined)
        const cats = result.lhr.categories
        const scores = {
          performance: Math.round((cats.performance?.score || 0) * 100),
          accessibility: Math.round((cats.accessibility?.score || 0) * 100),
          bestPractices: Math.round((cats['best-practices']?.score || 0) * 100),
          seo: Math.round((cats.seo?.score || 0) * 100),
        }
        const audits = result.lhr.audits
        reports.push({
          page: screen.name, formFactor, path: screen.path, scores,
          lcp: audits['largest-contentful-paint']?.numericValue,
          cls: audits['cumulative-layout-shift']?.numericValue,
          tbt: audits['total-blocking-time']?.numericValue,
          fcp: audits['first-contentful-paint']?.numericValue,
        })
        console.log(`lh ${formFactor} ${screen.name}: perf=${scores.performance} a11y=${scores.accessibility}`)
      } catch (e) {
        reports.push({ page: screen.name, formFactor, path: screen.path, error: String(e) })
        console.error(`lh FAIL ${formFactor} ${screen.name}`, e.message || e)
      }
    }
  }
  await chrome.kill()
  return reports
}

mkdirSync(OUT, { recursive: true })
const browser = await chromium.launch({ headless: true })
const axeLight = await runAxe(browser, 'light')
const axeDark = await runAxe(browser, 'dark')
await browser.close()
const lh = await runLighthouse()

const summary = {
  base: BASE,
  at: new Date().toISOString(),
  axe: {
    light: axeLight,
    dark: axeDark,
    totals: {
      light: sumViolations(axeLight),
      dark: sumViolations(axeDark),
    },
  },
  lighthouse: lh,
}

function sumViolations(rows) {
  const t = { pages: 0, violations: 0, critical: 0, serious: 0, moderate: 0, minor: 0, errors: 0 }
  for (const r of rows) {
    if (r.error) { t.errors += 1; continue }
    t.pages += 1
    t.violations += r.violations
    for (const k of ['critical', 'serious', 'moderate', 'minor']) t[k] += r.byImpact?.[k] || 0
  }
  return t
}

writeFileSync(join(OUT, 'summary.json'), JSON.stringify(summary, null, 2))
writeFileSync(join(OUT, 'axe-details.json'), JSON.stringify({ light: axeLight, dark: axeDark }, null, 2))
console.log('WROTE', join(OUT, 'summary.json'))
console.log('TOTALS', JSON.stringify(summary.axe.totals, null, 2))
