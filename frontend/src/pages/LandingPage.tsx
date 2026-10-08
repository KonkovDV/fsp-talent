import { Link } from 'react-router-dom'
import { BadgeCheck, FileSignature, ShieldCheck } from 'lucide-react'
import { SiteFooter } from '../components/Layout'
import { PublicHeader } from '../components/PublicShell'
import RussiaNetwork from '../components/RussiaNetwork'
import { CategoryPlate } from '../components/ui'
import { GRADES, ROLE_RU, gradeRu } from '../labels'

/** Illustrative rows for the protocol preview. They show the real card format; the people are invented. */
const SAMPLE = [
  { place: 1, role: 'backend', grade: 'senior', score: 91, evidence: ['Тест: 96 %', 'КМС, алгоритмическое'],
    factors: [100, 100, 100, 96, 80] },
  { place: 2, role: 'backend', grade: 'middle', score: 84, evidence: ['Тест: 88 %', 'Без истории ФСП'],
    factors: [92, 100, 100, 88, null] },
  { place: 3, role: 'fullstack', grade: 'middle', score: 71, evidence: ['Грейд не подтверждён', 'I разряд, продуктовое'],
    factors: [80, 85, 50, 50, 60] },
]
const FACTOR_NAMES = ['Навыки', 'Грейд', 'Роль', 'Тест', 'ФСП']

function ProtocolPreview() {
  return (
    <figure className="overflow-hidden rounded-2xl border border-line-strong/70 bg-panel shadow-lift dark:border-line" aria-label="Пример подборки">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-sunken/60 px-5 py-3.5">
        <span className="font-display text-sm font-bold text-ink">Потребность: backend, мидл</span>
        <span className="text-xs text-ink-3">Python, PostgreSQL. Пример выдачи</span>
      </figcaption>
      <ol className="divide-y divide-line">
        {SAMPLE.map((row, i) => (
          <li key={row.place} className="grid grid-cols-[1.75rem_1fr_auto] items-start gap-x-3 gap-y-2 px-4 py-4 sm:grid-cols-[2.25rem_1fr_auto] sm:gap-x-4 sm:px-5">
            <span className={`place pt-0.5 ${i === 0 ? 'text-accent' : 'text-ink-3'}`}>{row.place}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
                <CategoryPlate role={row.role} grade={row.grade} source={row.evidence[0].startsWith('Тест') ? 'assessed' : 'declared'} />
                {row.evidence.map(e => <span key={e} className="text-xs text-ink-2">{e}</span>)}
              </div>
              <div className="mt-3 grid grid-cols-5 gap-1.5" aria-hidden>
                {row.factors.map((f, k) => (
                  <div key={k}>
                    <div className="meter">{f !== null && <span style={{ width: `${f}%`, animationDelay: `${150 + i * 120 + k * 40}ms` }} />}</div>
                    <p className={`mt-1 truncate text-[10px] text-ink-3 ${f === null ? 'line-through' : ''}`}>{FACTOR_NAMES[k]}</p>
                  </div>
                ))}
              </div>
            </div>
            <span className="text-right">
              <span className="block font-display text-[1.75rem] font-bold leading-none tabular-nums text-ink">{row.score}</span>
              <span className="text-2xs text-ink-3">из 100</span>
            </span>
          </li>
        ))}
      </ol>
      <p className="border-t border-line px-5 py-3 text-xs text-ink-2">
        У второго кандидата нет истории ФСП — эта ось не учитывается и не тянет его вниз.
      </p>
    </figure>
  )
}

/** Illustrative showcase: how many people stand in each category. The real one is in the employer's search. */
const SHOWCASE_ROLES = ['backend', 'frontend', 'ml', 'security'] as const
const SHOWCASE: Record<string, number[]> = {
  backend: [6, 14, 23, 11, 4], frontend: [5, 12, 17, 8, 0], ml: [0, 7, 12, 6, 0], security: [0, 6, 9, 5, 0],
}
const SHOWCASE_GRADES = GRADES.slice(0, 4)

function Showcase() {
  const max = 23
  return (
    <figure className="rounded-2xl border border-line-strong/70 bg-panel p-4 shadow-xs dark:border-line sm:p-5">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-display text-sm font-bold text-ink">Витрина категорий</span>
        <span className="text-xs text-ink-3">пример, людей в поиске</span>
      </figcaption>
      <table className="mt-3 w-full table-fixed border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th scope="col" className="w-[28%] text-left font-normal text-ink-3 sm:w-[34%]"><span className="sr-only">Специализация</span></th>
            {SHOWCASE_GRADES.map(g => <th key={g} scope="col" className="pb-1 text-center text-[10px] font-medium text-ink-3 sm:text-xs">{gradeRu(g)}</th>)}
          </tr>
        </thead>
        <tbody>
          {SHOWCASE_ROLES.map(role => (
            <tr key={role}>
              <th scope="row" className="truncate pr-1 text-left font-medium text-ink">{role === 'security' ? 'ИБ' : ROLE_RU[role]}</th>
              {SHOWCASE[role].slice(0, 4).map((n, k) => {
                const focus = role === 'backend' && k === 2
                const r = n / max
                const level = n === 0 ? 0 : r > 0.75 ? 0.85 : r > 0.45 ? 0.45 : r > 0.25 ? 0.25 : 0.1
                return (
                  <td key={k} className={`h-9 rounded-md text-center font-display font-bold tabular-nums ${focus ? 'ring-2 ring-invite ring-offset-1 ring-offset-panel' : ''} ${level > 0.8 ? 'text-accent-ink' : 'text-ink'}`}
                    style={{ background: n === 0 ? 'rgb(var(--sunken))' : `rgb(var(--accent) / ${level.toFixed(2)})` }}>
                    {n === 0 ? <span className="font-sans font-normal text-ink-3">—</span> : n}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-ink-2">Работодатель выбирает ячейку «специализация × грейд» и сам пишет тем, кто в ней стоит.</p>
    </figure>
  )
}

const CANDIDATE_STEPS = [
  ['Регистрация по email', 'ФСП ID не обязателен — его можно привязать позже.'],
  ['Опрос', 'Специализация, сфера компании, заявленный грейд.'],
  ['Адаптивный тест', '8–20 заданий; у каждого кандидата свои.'],
  ['Приглашения', 'Работодатель пишет первым и сразу называет зарплату.'],
]
const EMPLOYER_STEPS = [
  ['Потребность', 'Роль, грейд, обязательные и желательные навыки.'],
  ['Подборка', 'Порядок задаёт один скор, у каждого фактора свой вес.'],
  ['Приглашение', 'Вилка до вычета НДФЛ и способ связи.'],
  ['Контакты', 'Открываются, когда кандидат принял приглашение.'],
]

function Lane({ title, steps, tone }: { title: string; steps: string[][]; tone: 'accent' | 'invite' }) {
  return (
    <div>
      <h3 className="flex items-center gap-2 font-display text-base font-bold text-ink">
        <span className={`h-2.5 w-2.5 rounded-full ${tone === 'accent' ? 'bg-accent' : 'bg-invite'}`} aria-hidden />{title}
      </h3>
      <ol className="mt-5 grid gap-0">
        {steps.map(([head, text], i) => (
          <li key={head} className="relative grid grid-cols-[2rem_1fr] gap-3 pb-5 last:pb-0">
            {i < steps.length - 1 && <span className="absolute left-[0.9375rem] top-8 bottom-1 w-px bg-line-strong" aria-hidden />}
            <span className="relative flex h-8 w-8 items-center justify-center rounded-full border border-line-strong bg-panel font-display text-xs font-bold tabular-nums text-ink-2">{i + 1}</span>
            <div className="pt-1">
              <p className="font-medium text-ink">{head}</p>
              <p className="mt-0.5 text-sm text-ink-2">{text}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

const TRUST = [
  { Icon: BadgeCheck, title: 'Задания проверяет код', text: 'Каждое задание собирается из шаблона, ответ получается запуском фрагмента: Python, JavaScript, Go, Java, Kotlin, C# или SQL. Утёкшие задания уходят в карантин автоматически.' },
  { Icon: FileSignature, title: 'Результаты ФСП подписаны', text: 'Место в протоколе выдаётся как удостоверение W3C VC 2.0. Подмена хотя бы одной цифры ломает проверку подписи.' },
  { Icon: ShieldCheck, title: 'Согласие — отдельный документ', text: 'Как требует 152-ФЗ с сентября 2025 года. Работодатель видит анонимную карточку, имя и контакты — только после согласия.' },
]

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-paper">
      <PublicHeader onBrand />

      <main id="main">
        <section className="relative isolate overflow-hidden bg-[#402FFF] text-white">
          <div className="mx-auto grid max-w-page items-center gap-10 px-4 pb-12 pt-10 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:pb-20 lg:pt-16">
            <div>
              <p className="text-sm text-white/85">Федерация спортивного программирования, ЛЦТ 2026</p>
              <h1 className="mt-5 font-display font-bold leading-[1.04] tracking-[-0.035em] [font-size:clamp(2.1rem,4.6vw,3.6rem)]">
                Приглашайте разработчиков по&nbsp;результату, а&nbsp;не по&nbsp;резюме
              </h1>
              <p className="mt-6 max-w-[52ch] text-lg leading-relaxed text-white/90">
                Кандидат проходит адаптивный тест и подтверждает достижения на соревнованиях ФСП. Работодатель видит
                категорию и объяснение подборки, а потом сам приглашает — сразу с зарплатной вилкой.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/register?role=employer" className="btn min-h-12 bg-white px-6 text-base text-[#2A1DD6] hover:bg-white/90">Найти кандидата</Link>
                <Link to="/register" className="btn min-h-12 border border-white/60 px-6 text-base text-white hover:bg-white/10">Я ищу работу</Link>
              </div>
              <div className="mt-8 max-w-xl rounded-xl border border-white/25 bg-white/[0.08] p-4 sm:p-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="font-display text-sm font-bold">Жюри: проверка за три минуты</p>
                  <Link to="/jury" className="btn-on-hero btn-sm">Маршрут для жюри</Link>
                </div>
                <p className="mt-2 text-sm text-white/90">
                  Демо-вход: <Link to="/login?role=employer" className="font-medium text-white underline">hr@sibcode.demo</Link> или{' '}
                  <Link to="/login" className="font-medium text-white underline">fsp001@demo.talent</Link>, пароль demo12345.
                </p>
              </div>
            </div>
            <figure>
              <RussiaNetwork onBrand className="h-auto w-full" />
              <figcaption className="mt-3 flex flex-wrap justify-between gap-2 border-t border-white/30 pt-3 font-display text-xs text-white/90">
                <span>89 региональных отделений ФСП</span>
                <span>один протокол, одни правила категории</span>
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="border-b border-line bg-panel" aria-labelledby="flow-title">
          <div className="mx-auto max-w-page px-4 py-14 sm:px-6 lg:py-20">
            <h2 id="flow-title" className="max-w-[24ch] font-display text-[1.75rem] font-bold leading-tight tracking-[-0.03em] text-ink sm:text-[2.125rem]">Работодатель ищет категорию, а не резюме</h2>
            <p className="mt-3 max-w-[60ch] text-ink-2">
              Обратный найм: кандидат один раз подтверждает уровень, дальше компании находят его сами и пишут первыми.
            </p>
            <div className="mt-10 grid items-start gap-10 lg:grid-cols-[1fr_1.1fr_1fr] lg:gap-8">
              <Lane title="Кандидату" steps={CANDIDATE_STEPS} tone="accent" />
              <Showcase />
              <Lane title="Работодателю" steps={EMPLOYER_STEPS} tone="invite" />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-page px-4 py-14 sm:px-6 lg:py-20">
          <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.15fr]">
            <div className="lg:pt-4">
              <h2 className="font-display text-[1.75rem] font-bold leading-tight tracking-[-0.03em] text-ink">Подборка читается как протокол</h2>
              <p className="mt-3 max-w-[48ch] text-ink-2">
                Место, категория «специализация × грейд», подтверждения и один скор. У каждого фактора своя полоса,
                а под карточкой — почему человек в выдаче и чего ему не хватает.
              </p>
              <dl className="mt-7 grid gap-4 text-sm">
                {[
                  ['Грейд подтверждает тест', 'Заявленный грейд помечен отдельно и весит меньше.'],
                  ['Результаты ФСП — отдельная ось', 'Нет истории соревнований — ось выключается и не штрафует.'],
                  ['Имя и регион не влияют на скор', 'Карточка анонимна до согласия кандидата.'],
                ].map(([dt, dd]) => (
                  <div key={dt} className="border-l-2 border-accent pl-4">
                    <dt className="font-medium text-ink">{dt}</dt><dd className="mt-0.5 text-ink-2">{dd}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <ProtocolPreview />
          </div>
        </section>

        <section className="border-t border-line bg-panel">
          <div className="mx-auto max-w-page px-4 py-14 sm:px-6 lg:py-20">
            <h2 className="font-display text-[1.75rem] font-bold leading-tight tracking-[-0.03em] text-ink">Почему категории можно верить</h2>
            <div className="mt-8 grid gap-8 md:grid-cols-3 md:gap-10">
              {TRUST.map(({ Icon, title, text }) => (
                <div key={title} className="border-t border-line-strong pt-5">
                  <span className="grid h-10 w-10 place-items-center rounded-lg bg-accent-soft text-accent" aria-hidden><Icon size={20} /></span>
                  <h3 className="mt-4 font-display text-base font-bold text-ink">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-2">{text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[#1B1C21] text-[#EDEDED]">
          <div className="mx-auto flex max-w-page flex-wrap items-center justify-between gap-6 px-4 py-12 sm:px-6 lg:py-14">
            <div>
              <h2 className="font-display text-2xl font-bold tracking-[-0.02em]">Опишите, кого ищете</h2>
              <p className="mt-2 text-sm text-[#C8C9CA]">Подборка с объяснением появится сразу после сохранения потребности.</p>
            </div>
            <Link to="/register?role=employer" className="btn min-h-12 bg-[#402FFF] px-6 text-white hover:bg-[#5444FF]">Создать аккаунт работодателя</Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
