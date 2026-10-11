/** Each value is also a cell in the README numbers table. The check reads this file. */
export const FIGURES: [string, string, string][] = [
  ['91,7 %', 'верных решений вдали от границы грейда, 2000 кандидатов', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,49', 'каппа Коэна повторного теста с новыми заданиями', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,24', 'медиана r, различающая сила вводимого ответа', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0 %', 'случайное угадывание проходит тест', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['64,5 %', 'точный итоговый грейд после пути по правилам продукта; в пределах ступени 98,9 %', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['41 %', 'максимальная доля показов одного ключа, 2000 кандидатов', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['72 %', 'максимальная доля показов одного ключа внутри специализации (mobile, js_eval:3); по всем специализациям 41 %', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,632', 'доля подходящих в первой десятке подбора, P@10 на размеченных парах, среднее трёх зёрен; сортировка по резюме — 0,559', 'cd backend && python -m app.validation.matching'],
  ['+0,089', 'подбор против поиска по ключевым словам (BM25 по словам потребности и профиля): разница nDCG@10, 95 % ДИ +0,068…+0,111, 232 потребности', 'cd backend && python -m app.validation.matching'],
  ['+0,038', 'подбор против сортировки по резюме (число заявленных нужных навыков, затем специализация и грейд): разница nDCG@10, 95 % ДИ +0,014…+0,061', 'cd backend && python -m app.validation.matching'],
]

/** When and on which commit the figures above were last printed by their commands. Update together with FIGURES. */
export const FIGURES_AS_OF = { date: '11.10.2026', commit: 'a63e4ca' }

export const SIMULATION_KEY_SHARE = FIGURES[5][0]

export function shareLabel(share: number): string {
  const tenths = Math.round(share * 1000) / 10
  const text = Number.isInteger(tenths) ? String(tenths) : tenths.toFixed(1).replace('.', ',')
  return `${text} %`
}
