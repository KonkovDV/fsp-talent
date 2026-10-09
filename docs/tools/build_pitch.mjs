// Slides that follow the mandatory LCT template slides 7–11.
// HTML is the source for the full-bleed images; build_pitch_template.py inserts them into the template.
// Every number carries the command that reproduces it.
//   node docs/tools/build_pitch.mjs && python docs/tools/build_pitch_template.py
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const feRequire = createRequire(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'frontend', 'package.json'))
const { chromium } = feRequire('playwright')
const dir = dirname(fileURLToPath(import.meta.url))
const docs = join(dir, '..')

const ink = '1B1C21'
const paper = 'F7F7F8'
const accent = '402FFF'
const red = 'EC1D35'
const muted = '5C5E66'

const A = 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'
const M = 'cd backend && python -m app.validation.matching'
const F = 'cd backend && python -m app.validation.fsp_axis --seeds 3'

// kind: text | shot | stats | end
const slides = [
  { kind: 'text', kicker: 'ПРОБЛЕМА И ОТВЕТ', title: 'Резюме обещает, тест подтверждает', cmd: M,
    notes: 'Работодатель приглашает первым. Грейд даёт только тест. ФСП — отдельная ось. Контакты после согласия.',
    items: [
      ['Проблема', 'Работодатель видит заявленный грейд и список технологий. Сортировка по резюме ставит в первую десятку 28 % людей с завышенным грейдом.'],
      ['Ответ', 'Грейд даёт только адаптивный тест специализации. Результаты ФСП — отдельная подтверждённая ось, без неё человек не теряет место.'],
      ['Механика', 'Работодатель описывает потребность, получает подборку с разбором каждого места и приглашает первым, сразу с вилкой.'],
    ] },
  { kind: 'shot', kicker: 'ПУТЬ КАНДИДАТА', title: 'Опрос, пробный тест, категория', img: 'assets/pitch-trial.png', alt: 'Пробный тест: шкала уверенности и нейтральный итог',
    notes: 'Пробный тест: 15 заданий за 5 минут, итог с вероятностью, грейд не ставится. Ключ чужого экземпляра сдаёт 0 %.',
    side: ['Кандидат выбирает специализацию и грейд, стаж только подсказывает.', 'Пробный тест: 15 заданий за 5 минут, нейтральный итог с вероятностью уровня.', 'Полный тест подтверждает грейд. Не сдали — ступень ниже доступна сразу.'] },
  { kind: 'shot', kicker: 'МЕХАНИКА КОНТАКТА', title: 'Приглашение с вилкой, контакты после согласия', img: 'assets/pitch-offers.png', alt: 'Приглашение с вилкой: имя и контакты открываются после согласия',
    notes: 'До принятия имени и контактов нет ни в карточке, ни в ответе API. Вилка обязательна и подписана «до вычета НДФЛ».',
    side: ['Карточки анонимны: имя и контакты открываются, только когда кандидат принял приглашение.', 'Не больше 50 приглашений в день от компании, срок ответа 14 дней.', 'После отказа та же компания ждёт 30 дней. Кандидат может закрыть контакты для одной компании.'] },
  { kind: 'stats', kicker: 'ТЕСТ', title: 'Выученный ответ не подходит', cmd: A,
    notes: '0 % — ключ от другого экземпляра того же семейства. 91,5 % — верные решения вдали от границы грейда, 2000 кандидатов. 0,0 % — сдача middle после 20 чужих сессий.',
    cells: [['0 %', 'сдают с ключом от другого экземпляра того же семейства'], ['91,5 %', 'верных решений вдали от границы грейда, 2000 кандидатов'], ['0,0 %', 'сдают middle после 20 чужих сессий; честная сдача тех же людей 6,2 %']] },
  { kind: 'shot', kicker: 'ПОДБОР', title: 'Доля подходящих в первой десятке', img: 'assets/pitch-card.png', alt: 'Карточка подборки: вклад теста и результатов ФСП в баллах', cmd: M,
    notes: 'P@10 0,632 против 0,559 у сортировки по резюме. Спирмен внутри категории 0,240 против 0,011. nDCG@10 0,652 против 0,620.',
    side: ['P@10 0,632 против 0,559 у сортировки по резюме: доля подходящих в первой десятке.', 'Спирмен 0,240 против 0,011: порядок внутри категории совпадает с настоящей силой.', 'nDCG@10 0,652 против 0,620. Завышенный грейд 19,8 % против 28,1 %.'] },
  { kind: 'end', kicker: 'ПРОВЕРЬТЕ САМИ', title: 'Жюри проходит тот же путь',
    notes: 'Аккаунты jury1…jury10, пароль demo12345. Инструкция запуска — docs/INSTALL.md. Стенд каждую ночь возвращается в исходное состояние.',
    items: ['Аккаунты jury1…jury10, пароль demo12345.', 'Инструкция запуска: docs/INSTALL.md', 'Репозиторий: github.com/KonkovDV/fsp-talent', 'Стенд каждую ночь в 04:10 возвращается в исходное состояние.'] },
  { kind: 'end', kicker: 'СПАСИБО', title: 'Вопросы',
    notes: 'Дальше — приложение для ответов на вопросы, его на защите не показываем.',
    items: ['Приложение к вопросам — следующие слайды.'] },
  { kind: 'stats', kicker: 'ПРИЛОЖЕНИЕ · ТОЧНОСТЬ', title: 'Решение о грейде держится', cmd: A,
    notes: '84 % — то же решение повторного теста вдали от порога. 65,1 % — точный грейд после пути по правилам продукта, в пределах ступени 98,6 %.',
    cells: [['84 %', 'то же решение повторного теста вдали от порога; корреляция θ 0,86, взвешенная каппа 0,58'], ['83,5 %', 'точность по Руднеру у порога; согласованность 79,0 %'], ['65,1 %', 'точный итоговый грейд после пути по правилам продукта; в пределах ступени 98,6 %']] },
  { kind: 'stats', kicker: 'ПРИЛОЖЕНИЕ · ОСЬ ФСП', title: 'Соревнования не поднимают грейд, статус не весит', cmd: F,
    notes: 'Спирмен нижней границы 0,707. Разряд — справка реестра. Ферма из 40 участий ниже двух побед.',
    cells: [['0,707', 'Спирмен нижней границы оси со скрытой силой. Разряд — справка из реестра, не расчёт по месту.'], ['0,127', 'Спирмен числа участий: нижняя граница угадывает силу лучше'], ['0,01 → 0,54', 'нижняя граница фермы из 40 онлайн-участий и двух побед']] },
  { kind: 'text', kicker: 'ПРИЛОЖЕНИЕ · НАДЁЖНОСТЬ', title: 'Проверяется в CI и на стенде',
    notes: 'Чужие идентификаторы: 124 запроса, 0 ответов 2xx. 708 юнит-тестов, покрытие приложения 66,1 %.',
    items: [
      ['Данные', 'Политики строк в PostgreSQL, обход всех маршрутов с чужим идентификатором: 0 ответов 2xx из 124 запросов (tests/smoke_api.py).'],
      ['152-ФЗ', 'Отдельные согласия с версией текста. Регистрация с 15 лет, для 15–17 — согласие представителя по ссылке. В GigaChat — только обезличенный текст и только по флагу.'],
      ['Сборка', '708 юнит-тестов, покрытие приложения 66,1 %, сервисы 72 % и API 39 %, 62 проверки Playwright: шесть сквозных сценариев и 56 проверок доступности. Демо-стенд сбрасывается каждую ночь.'],
    ] },
  { kind: 'end', kicker: 'ПРИЛОЖЕНИЕ · ДАЛЬШЕ', title: 'Пилот с Федерацией',
    notes: 'Подключить ФСП ID и реестр по готовому контракту. Калибровка весов — на исходах приглашений.',
    items: ['Подключить ФСП ID и реестр протоколов по готовому контракту OIDC.', 'Откалибровать веса подбора на исходах приглашений и найма.', 'Шифрование контактов в базе — отдельная миграция, когда будет известен срок.'] },
]

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

function htmlSlide(s) {
  const dark = s.kind === 'end'
  const head = `<div class="kicker">${esc(s.kicker)}</div><h1>${esc(s.title)}</h1>`
  let body = ''
  if (s.kind === 'text') body = s.items.map(([k, v]) => `<div class="card"><b>${esc(k)}.</b> ${esc(v)}</div>`).join('')
  if (s.kind === 'end') body = '<ul>' + s.items.map(v => `<li>${esc(v)}</li>`).join('') + '</ul>'
  if (s.kind === 'stats') body = '<div class="grid">' + s.cells.map(([n, t]) => `<div class="card"><div class="num">${esc(n)}</div><p>${esc(t)}</p></div>`).join('') + '</div>'
  if (s.kind === 'shot') body = `<div class="shot"><img src="${s.img}" alt="${esc(s.alt)}"><ul>${s.side.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>`
  const cmd = s.cmd ? `<p class="cmd">${esc(s.cmd)}</p>` : ''
  return `<section class="${dark ? 'dark' : 'light'}" data-notes="${esc(s.notes)}" data-alt="${esc(s.alt || s.title)}"><div class="bar"></div><div class="red"></div><div class="pad">${head}${body}${cmd}</div></section>`
}

const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>ФСП Талант — питч</title><style>
  @page { size: 13.333in 7.5in; margin: 0; }
  body { margin: 0; font-family: Arial, sans-serif; }
  section { width: 13.333in; height: 7.5in; page-break-after: always; box-sizing: border-box; position: relative; overflow: hidden; }
  section:last-child { page-break-after: auto; }
  .dark { background: #${ink}; color: #fff; } .light { background: #${paper}; color: #${ink}; }
  .bar { position: absolute; left: 0; top: 0; bottom: 0; width: 0.12in; background: #${accent}; }
  .red { position: absolute; left: 0.12in; top: 0; bottom: 0; width: 0.06in; background: #${red}; }
  .pad { padding: 0.45in 0.55in 0.35in 0.5in; }
  h1 { font-size: 32px; line-height: 1.15; margin: 0.08in 0 0.18in; }
  .kicker { color: #${accent}; font-size: 13px; letter-spacing: 0.08em; } .dark .kicker { color: #C8C9CA; }
  .card { background: #fff; border-radius: 8px; padding: 0.16in 0.24in; margin: 0.1in 0; font-size: 18px; }
  .num { color: #${accent}; font-size: 32px; font-weight: 700; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.18in; margin-top: 0.25in; } .grid p { font-size: 16px; }
  .shot { display: grid; grid-template-columns: 7.6in 1fr; gap: 0.28in; align-items: start; }
  .shot img { width: 7.6in; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,.15); }
  .shot li, .dark li { font-size: 18px; margin-bottom: 0.14in; line-height: 1.35; }
  .cmd { position: absolute; left: 0.5in; bottom: 0.22in; color: #${muted}; font: 12px 'Courier New', monospace; }
  .dark .cmd { color: #C8C9CA; }
</style></head><body>
${slides.map(htmlSlide).join('\n')}
</body></html>
`
writeFileSync(join(docs, 'pitch.html'), html)

const outDir = join(docs, 'assets', 'pitch-slides')
mkdirSync(outDir, { recursive: true })
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5 })
await page.goto(pathToFileURL(join(docs, 'pitch.html')).href)
const sections = page.locator('section')
const count = await sections.count()
const manifest = []
for (let i = 0; i < count; i++) {
  const section = sections.nth(i)
  const file = `${String(i + 1).padStart(2, '0')}.png`
  await section.screenshot({ path: join(outDir, file) })
  manifest.push({
    file,
    alt: await section.getAttribute('data-alt'),
    notes: await section.getAttribute('data-notes'),
  })
}
await browser.close()
writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2))
console.log('pitch.html and', count, 'slide images')
