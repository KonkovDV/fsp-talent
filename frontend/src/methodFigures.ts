/** Each value is also a cell in the README numbers table. The check reads this file. */
export const FIGURES: [string, string, string][] = [
  ['91,5 %', 'верных решений вдали от границы грейда, 2000 кандидатов', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,47', 'каппа Коэна повторного теста с новыми заданиями', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0,22', 'медиана r, различающая сила вводимого ответа', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['0 %', 'случайное угадывание проходит тест', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['65,1 %', 'точный итоговый грейд после пути по правилам продукта; в пределах ступени 98,6 %', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
  ['34 %', 'максимальная доля показов одного ключа, 2000 кандидатов', 'cd backend && python -m app.validation.assessment --n 2000 --seed 7'],
]

export const SIMULATION_KEY_SHARE = FIGURES[5][0]

export function shareLabel(share: number): string {
  const tenths = Math.round(share * 1000) / 10
  const text = Number.isInteger(tenths) ? String(tenths) : tenths.toFixed(1).replace('.', ',')
  return `${text} %`
}
