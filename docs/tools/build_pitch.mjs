// Ten slides for the jury from one source: docs/pitch.html (printed to docs/pitch.pdf by build_pdf.py --pitch)
// and docs/pitch.pptx. Every number carries the command that reproduces it.
//   npm install --prefix docs/tools && node docs/tools/build_pitch.mjs && python3 docs/tools/build_pdf.py --pitch
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const PptxGenJS = require('pptxgenjs')
const dir = dirname(fileURLToPath(import.meta.url))
const docs = join(dir, '..')

const ink = '1B1C21'
const paper = 'F7F7F8'
const accent = '402FFF'
const red = 'EC1D35'
const muted = '5C5E66'

const A = 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'
const M = 'cd backend && python -m app.validation.matching'

// kind: cover | text | shot | stats | end
const slides = [
  { kind: 'cover', kicker: 'ЛЦТ 2026 · ФЕДЕРАЦИЯ СПОРТИВНОГО ПРОГРАММИРОВАНИЯ', title: 'ФСП Талант: работодатель находит человека, а не наоборот',
    lead: 'Подтверждённый тестом грейд, объяснимая подборка и контакты только после согласия кандидата.' },
  { kind: 'text', kicker: 'ПРОБЛЕМА И ОТВЕТ', title: 'Резюме обещает, тест подтверждает', cmd: M,
    items: [
      ['Проблема', 'Работодатель видит заявленный грейд и список технологий. Сортировка по резюме ставит в первую десятку 28 % людей с завышенным грейдом.'],
      ['Ответ', 'Грейд даёт только адаптивный тест специализации. Результаты ФСП — отдельная подтверждённая ось, без неё человек не теряет место.'],
      ['Механика', 'Работодатель описывает потребность, получает подборку с разбором каждого места и приглашает первым, сразу с вилкой.'],
    ] },
  { kind: 'shot', kicker: 'ПУТЬ ЗА ТРИ МИНУТЫ', title: 'Опрос, пробный тест, категория', img: 'assets/pitch-trial.png', alt: 'Пробный тест: шкала уверенности и нейтральный итог',
    side: ['Кандидат выбирает специализацию и грейд, стаж только подсказывает.', 'Пробный тест: 15 заданий за 5 минут и нейтральный итог с вероятностью уровня.', 'Проверить самим: jury1…jury10, пароль demo12345.', 'Репозиторий: github.com/KonkovDV/fsp-talent'] },
  { kind: 'shot', kicker: 'МЕХАНИКА КОНТАКТА', title: 'Приглашение с вилкой, контакты после согласия', img: 'assets/pitch-offers.png', alt: 'Приглашение с вилкой: имя и контакты открываются после согласия',
    side: ['Карточки анонимны: имя и контакты открываются, только когда кандидат принял приглашение.', 'Не больше 50 приглашений в день от компании, срок ответа 14 дней.', 'После отказа та же компания ждёт 30 дней. Кандидат может закрыть контакты для одной компании.'] },
  { kind: 'stats', kicker: 'ТЕСТ', title: 'Выученный ответ не подходит', cmd: A,
    cells: [['0 %', 'сдают с ключом от другого экземпляра того же семейства'], ['100 %', 'сдали бы с ключом фиксированного банка вопросов'], ['0,0 %', 'сдают middle после 20 чужих сессий; честная сдача тех же людей 6,2 %']] },
  { kind: 'stats', kicker: 'ТОЧНОСТЬ И УСТОЙЧИВОСТЬ', title: 'Решение о грейде держится', cmd: A,
    cells: [['91,5 %', 'верных решений вдали от границы грейда, 2000 кандидатов'], ['84 %', 'то же решение повторного теста вдали от порога; корреляция θ 0,86, взвешенная каппа 0,58. Руднер 83,5 % и 79,0 %'], ['65,1 %', 'точный итоговый грейд после пути по правилам продукта; в пределах ступени 98,6 %']] },
  { kind: 'shot', kicker: 'ПОДБОР', title: 'Место в списке можно разобрать', img: 'assets/pitch-card.png', alt: 'Карточка подборки: вклад теста и результатов ФСП в баллах', cmd: M,
    side: ['В первой десятке людей с завышенным грейдом: 19,8 % против 28,1 % у сортировки по резюме.', 'Спирмен 0,240 против 0,011: насколько порядок совпадает с настоящей силой.', 'nDCG@10 0,652 против 0,620. Ярус в порядок не вошёл: он теряет это совпадение.'] },
  { kind: 'stats', kicker: 'ОСЬ ФСП', title: 'Соревнования не поднимают грейд, а уточняют порядок', cmd: 'cd backend && python -m app.validation.fsp_axis --seeds 3',
    cells: [['0,707', 'Спирмен нижней границы оси со скрытой силой'], ['0,127', 'Спирмен числа участий: нижняя граница угадывает силу лучше'], ['0,01 → 0,54', 'нижняя граница фермы из 40 онлайн-участий и двух побед']] },
  { kind: 'text', kicker: 'НАДЁЖНОСТЬ И ЗАКОН', title: 'Проверяется в CI и на стенде',
    items: [
      ['Данные', 'Политики строк в PostgreSQL, обход всех маршрутов с чужим идентификатором: 0 ответов 2xx из 124 запросов (tests/smoke_api.py).'],
      ['152-ФЗ', 'Отдельные согласия с версией текста. Регистрация с 15 лет, для 15–17 — согласие представителя по ссылке. В GigaChat — только обезличенный текст и только по флагу.'],
      ['Сборка', '679 юнит-тестов, покрытие приложения 66,4 %, сервисы 71 % и API 40 %, четыре сквозных сценария в браузере.'],
    ] },
  { kind: 'end', kicker: 'ЧТО ДАЛЬШЕ', title: 'Пилот с Федерацией',
    items: ['Подключить ФСП ID и реестр протоколов по готовому контракту OIDC.', 'Откалибровать веса подбора на исходах приглашений и найма.', 'Открыть стенд для команд-участников ФСП и работодателей-партнёров.'] },
]

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

function htmlSlide(s, i) {
  const dark = s.kind === 'cover' || s.kind === 'end'
  const head = `<div class="kicker">${esc(s.kicker)}</div><h1>${esc(s.title)}</h1>`
  let body = ''
  if (s.kind === 'cover') body = `<p class="lead">${esc(s.lead)}</p>`
  if (s.kind === 'text') body = s.items.map(([k, v]) => `<div class="card"><b>${esc(k)}.</b> ${esc(v)}</div>`).join('')
  if (s.kind === 'end') body = '<ul>' + s.items.map(v => `<li>${esc(v)}</li>`).join('') + '</ul>'
  if (s.kind === 'stats') body = '<div class="grid">' + s.cells.map(([n, t]) => `<div class="card"><div class="num">${esc(n)}</div><p>${esc(t)}</p></div>`).join('') + '</div>'
  if (s.kind === 'shot') body = `<div class="shot"><img src="${s.img}" alt="${esc(s.alt)}"><ul>${s.side.map(v => `<li>${esc(v)}</li>`).join('')}</ul></div>`
  const cmd = s.cmd ? `<p class="cmd">${esc(s.cmd)}</p>` : ''
  return `<section class="${dark ? 'dark' : 'light'}"><div class="bar"></div><div class="red"></div><div class="pad${s.kind === 'cover' ? ' cover' : ''}">${head}${body}${cmd}</div><div class="page">${i + 1} / ${slides.length}</div></section>`
}

const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>ФСП Талант — питч</title><style>
  @page { size: 13.333in 7.5in; margin: 0; }
  body { margin: 0; font-family: Arial, sans-serif; }
  section { width: 13.333in; height: 7.5in; page-break-after: always; box-sizing: border-box; position: relative; overflow: hidden; }
  section:last-child { page-break-after: auto; }
  .dark { background: #${ink}; color: #fff; } .light { background: #${paper}; color: #${ink}; }
  .bar { position: absolute; left: 0; top: 0; bottom: 0; width: 0.12in; background: #${accent}; }
  .red { position: absolute; left: 0.12in; top: 0; bottom: 0; width: 0.06in; background: #${red}; }
  .pad { padding: 0.5in 0.6in 0.4in 0.55in; } .cover { padding-top: 1.7in; }
  h1 { font-size: 34px; line-height: 1.15; margin: 0.12in 0 0.2in; }
  .kicker { color: #${accent}; font-size: 13px; letter-spacing: 0.08em; } .dark .kicker { color: #C8C9CA; }
  .lead { font-size: 20px; color: #EDEDED; max-width: 10in; }
  .card { background: #fff; border-radius: 8px; padding: 0.2in 0.28in; margin: 0.12in 0; font-size: 18px; }
  .num { color: #${accent}; font-size: 34px; font-weight: 700; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.2in; margin-top: 0.3in; } .grid p { font-size: 17px; }
  .shot { display: grid; grid-template-columns: 7.6in 1fr; gap: 0.3in; align-items: start; }
  .shot img { width: 7.6in; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,.15); }
  .shot li, .dark li { font-size: 18px; margin-bottom: 0.16in; line-height: 1.35; }
  .cmd { position: absolute; left: 0.55in; bottom: 0.3in; color: #${muted}; font: 13px monospace; }
  .page { position: absolute; right: 0.4in; bottom: 0.3in; font-size: 12px; color: #${muted}; }
</style></head><body>
${slides.map(htmlSlide).join('\n')}
</body></html>
`
writeFileSync(join(docs, 'pitch.html'), html)

const pres = new PptxGenJS()
pres.defineLayout({ name: 'PITCH', width: 13.333, height: 7.5 })
pres.layout = 'PITCH'
pres.author = 'Konkov Dmitrij'
pres.company = 'ФСП Талант'
pres.title = 'ФСП Талант — обратный найм'
pres.subject = 'Десять слайдов для жюри ЛЦТ 2026'
const T = { fontFace: 'Arial', margin: 0 }

slides.forEach((s, i) => {
  const slide = pres.addSlide()
  const dark = s.kind === 'cover' || s.kind === 'end'
  slide.background = { color: dark ? ink : paper }
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 7.5, fill: { color: accent } })
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.12, y: 0, w: 0.06, h: 7.5, fill: { color: red } })
  const top = s.kind === 'cover' ? 1.7 : 0.5
  slide.addText(s.kicker, { ...T, x: 0.55, y: top, w: 12, h: 0.3, fontSize: 12, color: dark ? 'C8C9CA' : accent, charSpacing: 2 })
  slide.addText(s.title, { ...T, x: 0.55, y: top + 0.35, w: 12.2, h: 1.0, fontSize: 30, bold: true, color: dark ? 'FFFFFF' : ink })
  if (s.kind === 'cover') slide.addText(s.lead, { ...T, x: 0.55, y: 3.3, w: 11, h: 1, fontSize: 20, color: 'EDEDED' })
  if (s.kind === 'text') s.items.forEach(([k, v], j) => {
    const y = 1.9 + j * 1.6
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.55, y, w: 12.2, h: 1.35, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF' }, rectRadius: 0.08 })
    slide.addText([{ text: k + '. ', options: { bold: true } }, { text: v }], { ...T, x: 0.8, y: y + 0.15, w: 11.7, h: 1.05, fontSize: 17, color: ink, valign: 'middle' })
  })
  if (s.kind === 'end') slide.addText(s.items.map(v => ({ text: v, options: { bullet: true, breakLine: true } })), { ...T, x: 0.55, y: 2.0, w: 12, h: 3.5, fontSize: 20, color: 'FFFFFF', paraSpaceAfter: 12 })
  if (s.kind === 'stats') s.cells.forEach(([n, t], j) => {
    const x = 0.55 + j * 4.13
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.1, w: 3.93, h: 3.2, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF' }, rectRadius: 0.08 })
    slide.addText(n, { ...T, x: x + 0.25, y: 2.35, w: 3.45, h: 0.9, fontSize: 30, bold: true, color: accent })
    slide.addText(t, { ...T, x: x + 0.25, y: 3.35, w: 3.45, h: 1.7, fontSize: 16, color: ink, valign: 'top' })
  })
  if (s.kind === 'shot') {
    slide.addImage({ path: join(docs, s.img), altText: s.alt, x: 0.55, y: 1.75, w: 7.6, h: 4.75 })
    slide.addText(s.side.map(v => ({ text: v, options: { bullet: true, breakLine: true } })), { ...T, x: 8.45, y: 1.75, w: 4.4, h: 4.75, fontSize: 16, color: ink, valign: 'top', paraSpaceAfter: 10 })
  }
  if (s.cmd) slide.addText(s.cmd, { ...T, x: 0.55, y: 6.85, w: 11, h: 0.3, fontSize: 11, fontFace: 'Courier New', color: muted })
  slide.addText(`${i + 1} / ${slides.length}`, { ...T, x: 11.9, y: 6.9, w: 1, h: 0.3, fontSize: 11, color: muted, align: 'right' })
})

await pres.writeFile({ fileName: join(docs, 'pitch.pptx') })
console.log('pitch.html and pitch.pptx:', slides.length, 'slides')
