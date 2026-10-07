import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const PptxGenJS = require('pptxgenjs')
const dir = dirname(fileURLToPath(import.meta.url))
const outDir = join(dir, '..')

const ink = '1B1C21'
const paper = 'F7F7F8'
const accent = '402FFF'
const red = 'EC1D35'
const muted = '5C5E66'
const white = 'FFFFFF'

const pres = new PptxGenJS()
pres.defineLayout({ name: 'PITCH', width: 13.333, height: 7.5 })
pres.layout = 'PITCH'
pres.author = 'ФСП Талант'
pres.title = 'ФСП Талант — обратный найм'
pres.subject = 'Семь слайдов для жюри ЛЦТ 2026'

function dark(slide) {
  slide.background = { color: ink }
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 7.5, fill: { color: accent } })
  slide.addShape(pres.shapes.RECTANGLE, { x: 0.12, y: 0, w: 0.06, h: 7.5, fill: { color: red } })
}

function light(slide, kicker) {
  slide.background = { color: paper }
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.12, h: 7.5, fill: { color: accent } })
  slide.addText(kicker, {
    x: 0.55, y: 0.32, w: 12, h: 0.32,
    fontFace: 'Arial', fontSize: 12, color: accent, margin: 0, charSpacing: 1.2,
  })
}

function title(slide, text, y, color) {
  slide.addText(text, {
    x: 0.55, y, w: 12.2, h: 1.15,
    fontFace: 'Arial', fontSize: 36, bold: true, color, margin: 0,
  })
}

const s1 = pres.addSlide()
dark(s1)
s1.addText('ЛЦТ 2026  ·  ФЕДЕРАЦИЯ СПОРТИВНОГО ПРОГРАММИРОВАНИЯ', {
  x: 0.55, y: 1.7, w: 12, h: 0.3, fontFace: 'Arial', fontSize: 13, color: 'C8C9CA', margin: 0,
})
title(s1, 'Работодатель находит человека.\nНе наоборот.', 2.15, white)
s1.addText('Подтверждённый профиль, объяснимая подборка и контакты только после согласия кандидата.', {
  x: 0.55, y: 4.7, w: 10.5, h: 0.7, fontFace: 'Arial', fontSize: 18, color: 'EDEDED', margin: 0,
})

const s2 = pres.addSlide()
light(s2, 'КАК УСТРОЕН НАЙМ')
title(s2, 'Потребность, подборка, приглашение', 0.7, ink)
const steps = [
  ['01', 'Кандидат', 'Опрос задаёт специализацию. Тест подтверждает грейд. История ФСП — отдельная ось, без неё человек не теряет место.'],
  ['02', 'Работодатель', 'Описывает, кого ищет. Получает порядок с объяснением каждой строки и может вернуть прошлую версию потребности.'],
  ['03', 'Контакты', 'Приглашение с вилкой. Имя и почта открываются, только когда кандидат принял приглашение.'],
]
steps.forEach((row, i) => {
  const y = 2.15 + i * 1.55
  s2.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.55, y, w: 12.2, h: 1.4, fill: { color: white }, rectRadius: 0.08,
  })
  s2.addText(row[0], { x: 0.8, y: y + 0.35, w: 1.1, h: 0.6, fontFace: 'Arial', fontSize: 22, bold: true, color: accent, margin: 0 })
  s2.addText(row[1], { x: 2.1, y: y + 0.22, w: 10, h: 0.4, fontFace: 'Arial', fontSize: 18, bold: true, color: ink, margin: 0 })
  s2.addText(row[2], { x: 2.1, y: y + 0.68, w: 10.2, h: 0.5, fontFace: 'Arial', fontSize: 15, color: muted, margin: 0 })
})

const s3 = pres.addSlide()
light(s3, 'ТЕСТ')
title(s3, 'Выученный ответ не подходит', 0.7, ink)
const facts = [
  ['0 %', 'сдают с ключом от другого экземпляра того же семейства'],
  ['100 %', 'сдают, если ключ от того же экземпляра, как в фиксированном банке'],
  ['18 из 37', 'утёкших ключей уходит в карантин, на чистых данных 5 из 68'],
]
facts.forEach((row, i) => {
  const x = 0.55 + i * 4.15
  s3.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y: 2.2, w: 3.95, h: 3.3, fill: { color: white }, rectRadius: 0.08,
  })
  s3.addText(row[0], { x: x + 0.25, y: 2.5, w: 3.45, h: 1.1, fontFace: 'Arial', fontSize: 32, bold: true, color: accent, margin: 0 })
  s3.addText(row[1], { x: x + 0.25, y: 3.8, w: 3.45, h: 1.3, fontFace: 'Arial', fontSize: 16, color: ink, margin: 0 })
})
s3.addText('python -m app.validation.assessment --n 2000 --seed 7', {
  x: 0.55, y: 6.75, w: 12, h: 0.3, fontFace: 'Arial', fontSize: 12, color: muted, margin: 0,
})

const s4 = pres.addSlide()
light(s4, 'ПОДБОР')
title(s4, 'Место в списке можно разобрать', 0.7, ink)
s4.addText('Навыки, грейд, специализация, текст и сфера складываются в одну оценку. У каждой строки объяснения свой код: совпадение, подтверждённый навык, тест, пробел, ось ФСП, смежная специализация.', {
  x: 0.55, y: 2.1, w: 12.2, h: 1.1, fontFace: 'Arial', fontSize: 18, color: ink, margin: 0,
})
const deltas = [
  ['+0,046', 'nDCG@10 к поиску по словам, зерно 2026'],
  ['+0,087', 'nDCG@10 к поиску по словам, зерно 7'],
]
deltas.forEach((row, i) => {
  const x = 0.55 + i * 6.3
  s4.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y: 3.5, w: 6.0, h: 2.2, fill: { color: white }, rectRadius: 0.08,
  })
  s4.addText(row[0], { x: x + 0.3, y: 3.75, w: 5.4, h: 0.8, fontFace: 'Arial', fontSize: 36, bold: true, color: accent, margin: 0 })
  s4.addText(row[1], { x: x + 0.3, y: 4.65, w: 5.4, h: 0.7, fontFace: 'Arial', fontSize: 16, color: ink, margin: 0 })
})
s4.addText('python -m app.validation.matching    и    python -m app.validation.matching --seed 7', {
  x: 0.55, y: 6.75, w: 12, h: 0.3, fontFace: 'Arial', fontSize: 12, color: muted, margin: 0,
})

const s5 = pres.addSlide()
light(s5, 'ОСЬ ФСП')
title(s5, 'Соревнования не поднимают грейд', 0.7, ink)
s5.addText('Грейд подтверждает только тест. Протокол ФСП — вторая ось: место, давность, командный зачёт. Статус соревнования на балл не влияет. Нет истории — ось выпадает из оценки, штрафа нет.', {
  x: 0.55, y: 2.15, w: 12.2, h: 1.2, fontFace: 'Arial', fontSize: 18, color: ink, margin: 0,
})
const axis = [
  ['0,661 и 0,661', 'nDCG@10 с осью и без неё, зерно 2026'],
  ['0,713 и 0,713', 'nDCG@10 с осью и без неё, зерно 7'],
]
axis.forEach((row, i) => {
  const y = 3.6 + i * 1.4
  s5.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.55, y, w: 12.2, h: 1.25, fill: { color: white }, rectRadius: 0.08,
  })
  s5.addText(row[0], { x: 0.85, y: y + 0.3, w: 4.2, h: 0.65, fontFace: 'Arial', fontSize: 26, bold: true, color: accent, margin: 0 })
  s5.addText(row[1], { x: 5.2, y: y + 0.35, w: 7, h: 0.55, fontFace: 'Arial', fontSize: 18, color: ink, margin: 0 })
})

const s6 = pres.addSlide()
light(s6, 'ПРОВЕРКА')
title(s6, 'Те же команды, что в документации', 0.7, ink)
const rows = [
  ['Точность вдали от границы грейда', '91,5 %', 'assessment --n 2000 --seed 7'],
  ['Повторная сдача, каппа Коэна', '0,51', 'та же команда'],
  ['Завышение грейда', '2,2 %', 'та же команда'],
  ['Случайное угадывание', '0 %', 'та же команда'],
  ['Подбор против ключевых слов', '+0,046 и +0,087', 'matching и --seed 7'],
]
rows.forEach((row, i) => {
  const y = 2.15 + i * 0.85
  s6.addShape(pres.shapes.RECTANGLE, {
    x: 0.55, y, w: 12.2, h: 0.75, fill: { color: i % 2 ? white : 'EFEFF1' },
  })
  s6.addText(row[0], { x: 0.75, y: y + 0.18, w: 6.2, h: 0.4, fontFace: 'Arial', fontSize: 16, color: ink, margin: 0 })
  s6.addText(row[1], { x: 7.0, y: y + 0.15, w: 2.4, h: 0.45, fontFace: 'Arial', fontSize: 18, bold: true, color: accent, margin: 0 })
  s6.addText(row[2], { x: 9.4, y: y + 0.18, w: 3.1, h: 0.4, fontFace: 'Arial', fontSize: 12, color: muted, margin: 0 })
})

const s7 = pres.addSlide()
dark(s7)
s7.addText('ДАЛЬШЕ', {
  x: 0.55, y: 0.45, w: 12, h: 0.3, fontFace: 'Arial', fontSize: 12, color: accent, margin: 0,
})
title(s7, 'Что остаётся за этим стендом', 0.85, white)
const later = [
  'Настоящий ФСП ID и реестр по уже описанному контракту. Дельта протоколов забирается по расписанию.',
  'Порог по слабой теме не включён: точность падает с 78,5 % до 55,4 %, ложные сдачи — с 7,7 % до 3,0 %.',
  'Оценку различимости заданий в банк не пишем: ошибка растёт с 0,146 до 0,283.',
  'Исходы найма из ATS, чтобы калибровать подбор на реальных решениях людей.',
]
later.forEach((line, i) => {
  s7.addText(line, {
    x: 0.55, y: 2.4 + i * 1.05, w: 12, h: 0.9,
    fontFace: 'Arial', fontSize: 18, color: 'EDEDED', margin: 0,
  })
})

s1.addNotes('Около сорока секунд. Работодатель ищет человека по подтверждённому результату, а не по резюме. Грейд даёт только тест. История ФСП — вторая ось: если истории нет, штрафа нет. Имя и почта открываются, когда кандидат принял приглашение. Дальше — как устроены тест и место в списке, и цифры, которые повторяются командой.')
s2.addNotes('Около пятидесяти секунд. Опрос задаёт специализацию. Тест подтверждает грейд. Работодатель описывает потребность и получает порядок, где у каждой строки есть объяснение. Прошлую версию потребности можно вернуть, отобранные из-за этого не пропадают. В приглашении — вилка до вычета НДФЛ. Контакты открываются только после согласия кандидата.')
s3.addNotes('Около пятидесяти секунд. Ключ от другого экземпляра того же семейства не проходит: сдают 0 %. Ключ от того же экземпляра, как в заранее опубликованном банке, даёт 100 %. Поэтому каждый кандидат получает новые экземпляры. Если ключ всё же утёк, карантин забирает 18 из 37 таких ключей. На чистых данных ложных тревог 5 из 68. Команда на слайде: две тысячи кандидатов, зерно 7.')
s4.addNotes('Около сорока секунд. Место складывается из навыков, грейда, специализации, текста и сферы. У строки объяснения есть код причины и, где источник ясен, метка: тест, ФСП, заявлено, вилка или очередь. Против поиска по словам nDCG@10 выше на 0,046 при зерне 2026 и на 0,087 при зерне 7.')
s5.addNotes('Около сорока секунд. Соревнования не поднимают грейд. Ось ФСП, версия 3.1.0, учитывает место, давность и командный зачёт. Статус соревнования на балл не влияет. Участие весит ноль, в сумму входят пять сильнейших событий. Кандидат без истории не теряет баллы: nDCG@10 равен 0,661 и с осью, и без неё на зерне 2026, и 0,713 в обоих случаях на зерне 7.')
s6.addNotes('Около пятидесяти секунд. Это те же команды, что в документации, прогон на 2000 кандидатов, зерно 7. Точность вдали от границы грейда — 91,5 %. Повторная сдача, каппа Коэна — 0,51. Завышение грейда — 2,2 %. Случайное угадывание — 0 %. Подбор против ключевых слов — те же +0,046 и +0,087. Регион в оценку не входит. На этом же прогоне четыре скрытые метки дают максимальную долю одного ключа 33 %, 35 %, 33 % и 37 %, отношение меньшей к большей — 0,88.')
s7.addNotes('Около сорока секунд, всего около пяти минут. Настоящий ФСП ID и реестр подключаются по уже описанному контракту. Порог по слабой теме не включён: точность падает с 78,5 % до 55,4 %, ложные сдачи — с 7,7 % до 3,0 %. Оценку различимости заданий в банк не пишем: ошибка растёт с 0,146 до 0,283. Веса подбора перекалибруем, когда появятся реальные исходы найма. Запасная запись — docs/pitch-backup.mp4: те же слайды и этот текст, без камеры.')

await pres.writeFile({ fileName: join(outDir, 'pitch.pptx') })

const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><style>
  @page { size: 13.333in 7.5in; margin: 0; }
  body { margin: 0; font-family: Arial, sans-serif; }
  section { width: 13.333in; height: 7.5in; page-break-after: always; box-sizing: border-box; position: relative; overflow: hidden; }
  section:last-child { page-break-after: auto; }
  .dark { background: #1B1C21; color: #fff; }
  .light { background: #F7F7F8; color: #1B1C21; }
  .bar { position: absolute; left: 0; top: 0; bottom: 0; width: 0.12in; background: #402FFF; }
  .red { position: absolute; left: 0.12in; top: 0; bottom: 0; width: 0.06in; background: #EC1D35; }
  .pad { padding: 0.55in 0.6in 0.4in 0.55in; }
  h1 { font-size: 36px; line-height: 1.15; margin: 0.2in 0; }
  .kicker { color: #402FFF; font-size: 13px; letter-spacing: 0.08em; }
  .card { background: #fff; border-radius: 8px; padding: 0.22in 0.28in; margin: 0.12in 0; }
  .num { color: #402FFF; font-size: 28px; font-weight: 700; }
  .muted { color: #5C5E66; font-size: 13px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.18in; margin-top: 0.3in; }
  .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 0.2in; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.2in; font-size: 16px; }
  td { padding: 0.12in 0.15in; }
  tr:nth-child(odd) td { background: #EFEFF1; }
</style></head><body>
<section class="dark"><div class="bar"></div><div class="red"></div><div class="pad" style="padding-top:1.7in">
  <div style="color:#C8C9CA;font-size:13px">ЛЦТ 2026 · ФЕДЕРАЦИЯ СПОРТИВНОГО ПРОГРАММИРОВАНИЯ</div>
  <h1>Работодатель находит человека.<br>Не наоборот.</h1>
  <p style="font-size:18px;color:#EDEDED;max-width:10in">Подтверждённый профиль, объяснимая подборка и контакты только после согласия кандидата.</p>
</div></section>
<section class="light"><div class="bar"></div><div class="pad">
  <div class="kicker">КАК УСТРОЕН НАЙМ</div><h1>Потребность, подборка, приглашение</h1>
  <div class="card"><b>01 Кандидат.</b> Опрос задаёт специализацию. Тест подтверждает грейд. История ФСП — отдельная ось, без неё человек не теряет место.</div>
  <div class="card"><b>02 Работодатель.</b> Описывает, кого ищет. Получает порядок с объяснением каждой строки и может вернуть прошлую версию потребности.</div>
  <div class="card"><b>03 Контакты.</b> Приглашение с вилкой. Имя и почта открываются, только когда кандидат принял приглашение.</div>
</div></section>
<section class="light"><div class="bar"></div><div class="pad">
  <div class="kicker">ТЕСТ</div><h1>Выученный ответ не подходит</h1>
  <div class="grid">
    <div class="card"><div class="num">0 %</div><p>сдают с ключом от другого экземпляра того же семейства</p></div>
    <div class="card"><div class="num">100 %</div><p>сдают, если ключ от того же экземпляра, как в фиксированном банке</p></div>
    <div class="card"><div class="num">18 из 37</div><p>утёкших ключей уходит в карантин, на чистых данных 5 из 68</p></div>
  </div>
  <p class="muted">python -m app.validation.assessment --n 2000 --seed 7</p>
</div></section>
<section class="light"><div class="bar"></div><div class="pad">
  <div class="kicker">ПОДБОР</div><h1>Место в списке можно разобрать</h1>
  <p style="font-size:18px">Навыки, грейд, специализация, текст и сфера складываются в одну оценку. У каждой строки объяснения свой код.</p>
  <div class="pair">
    <div class="card"><div class="num">+0,046</div><p>nDCG@10 к поиску по словам, зерно 2026</p></div>
    <div class="card"><div class="num">+0,087</div><p>nDCG@10 к поиску по словам, зерно 7</p></div>
  </div>
  <p class="muted">python -m app.validation.matching и --seed 7</p>
</div></section>
<section class="light"><div class="bar"></div><div class="pad">
  <div class="kicker">ОСЬ ФСП</div><h1>Соревнования не поднимают грейд</h1>
  <p style="font-size:18px">Грейд подтверждает только тест. Нет истории ФСП — ось выпадает из оценки, штрафа нет.</p>
  <div class="card"><span class="num">0,661 и 0,661</span> nDCG@10 с осью и без неё, зерно 2026</div>
  <div class="card"><span class="num">0,713 и 0,713</span> nDCG@10 с осью и без неё, зерно 7</div>
</div></section>
<section class="light"><div class="bar"></div><div class="pad">
  <div class="kicker">ПРОВЕРКА</div><h1>Те же команды, что в документации</h1>
  <table>
    <tr><td>Точность вдали от границы грейда</td><td class="num">91,5 %</td><td class="muted">assessment --n 2000 --seed 7</td></tr>
    <tr><td>Повторная сдача, каппа Коэна</td><td class="num">0,51</td><td class="muted">та же команда</td></tr>
    <tr><td>Завышение грейда</td><td class="num">2,2 %</td><td class="muted">та же команда</td></tr>
    <tr><td>Случайное угадывание</td><td class="num">0 %</td><td class="muted">та же команда</td></tr>
    <tr><td>Подбор против ключевых слов</td><td class="num">+0,046 и +0,087</td><td class="muted">matching и --seed 7</td></tr>
  </table>
</div></section>
<section class="dark"><div class="bar"></div><div class="red"></div><div class="pad">
  <div class="kicker">ДАЛЬШЕ</div><h1>Что остаётся за этим стендом</h1>
  <p>Настоящий ФСП ID и реестр по уже описанному контракту. Дельта протоколов забирается по расписанию.</p>
  <p>Порог по слабой теме не включён: точность падает с 78,5 % до 55,4 %, ложные сдачи — с 7,7 % до 3,0 %.</p>
  <p>Оценку различимости заданий в банк не пишем: ошибка растёт с 0,146 до 0,283.</p>
  <p>Исходы найма из ATS, чтобы калибровать подбор на реальных решениях людей.</p>
</div></section>
</body></html>`
writeFileSync(join(outDir, 'pitch.html'), html)
console.log('wrote pitch.pptx and pitch.html')
