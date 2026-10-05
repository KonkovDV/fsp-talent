import { Link } from 'react-router-dom'
import { BadgeCheck, FileSignature, ShieldCheck } from 'lucide-react'
import { SiteFooter } from '../components/Layout'
import { PublicHeader } from '../components/PublicShell'
import RussiaNetwork from '../components/RussiaNetwork'

/** Illustrative rows for the hero. They show the real card format; the people are invented. */
const SAMPLE = [
  { place: 1, cat: 'backend · senior', grade: 'senior', score: 91, evidence: ['Тест: 96 %', 'КМС, алгоритмическое'],
    factors: [100, 100, 100, 96, 80] },
  { place: 2, cat: 'backend · middle', grade: 'middle', score: 84, evidence: ['Тест: 88 %', 'Без истории ФСП'],
    factors: [92, 100, 100, 88, null] },
  { place: 3, cat: 'fullstack · middle', grade: 'middle', score: 71, evidence: ['Грейд заявлен', 'I разряд, продуктовое'],
    factors: [80, 85, 50, 50, 60] },
]
const FACTOR_NAMES = ['Навыки', 'Грейд', 'Роль', 'Тест', 'ФСП']

function ProtocolPreview() {
  return (
    <figure className="rounded-xl border border-line bg-panel shadow-pop" aria-label="Пример подборки">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-5 py-4">
        <span className="font-display text-sm font-bold text-ink">Потребность: backend, middle</span>
        <span className="text-xs text-ink-3">Python, PostgreSQL · пример выдачи</span>
      </figcaption>
      <ol className="divide-y divide-line">
        {SAMPLE.map((row, i) => (
          <li key={row.place} className="grid grid-cols-[2.25rem_1fr_auto] items-center gap-x-4 gap-y-2 px-5 py-4">
            <span className="place text-ink-3">{row.place}</span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`badge-${row.grade}`}>{row.cat}</span>
                {row.evidence.map(e => <span key={e} className="text-xs text-ink-2">{e}</span>)}
              </div>
              <div className="mt-2.5 grid grid-cols-5 gap-1.5" aria-hidden>
                {row.factors.map((f, k) => (
                  <div key={k}>
                    <div className="meter">{f !== null && <span style={{ width: `${f}%`, animationDelay: `${150 + i * 120 + k * 40}ms` }} />}</div>
                    <p className={`mt-1 truncate text-[10px] ${f === null ? 'text-ink-3 line-through' : 'text-ink-3'}`}>{FACTOR_NAMES[k]}</p>
                  </div>
                ))}
              </div>
            </div>
            <span className="text-right">
              <span className="block font-display text-2xl font-bold tabular-nums text-ink">{row.score}</span>
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

const CANDIDATE_STEPS = [
  ['Регистрация по email', 'ФСП ID не обязателен — его можно привязать позже.'],
  ['Опрос', 'Специализация, отрасль, заявленный грейд.'],
  ['Адаптивный тест', '8–20 заданий; у каждого кандидата свои.'],
  ['Приглашения', 'Работодатель пишет первым и сразу называет зарплату.'],
]
const EMPLOYER_STEPS = [
  ['Потребность', 'Роль, грейд, обязательные и желательные навыки.'],
  ['Подборка', 'Порядок задаёт один скор, у каждого фактора свой вес.'],
  ['Приглашение', 'Зарплата «от» и «до» в рублях и способ связи.'],
  ['Контакты', 'Открываются, когда кандидат принял приглашение.'],
]

function Lane({ title, steps }: { title: string; steps: string[][] }) {
  return (
    <div>
      <h3 className="section-title">{title}</h3>
      <ol className="mt-5 space-y-5">
        {steps.map(([head, text], i) => (
          <li key={head} className="grid grid-cols-[2rem_1fr] gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-full border border-line-strong text-xs font-semibold tabular-nums text-ink-2">{i + 1}</span>
            <div>
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
  { Icon: BadgeCheck, title: 'Задания проверяет код', text: 'Каждое задание собирается из шаблона, ответ получается запуском фрагмента: Python, JavaScript, Go, Java или SQL. Утёкшие задания уходят в карантин автоматически.' },
  { Icon: FileSignature, title: 'Результаты ФСП подписаны', text: 'Место в протоколе выдаётся как удостоверение W3C VC 2.0. Подмена хотя бы одной цифры ломает проверку подписи.' },
  { Icon: ShieldCheck, title: 'Согласие — отдельный документ', text: 'Как требует 152-ФЗ с сентября 2025 года. Работодатель видит анонимную карточку, имя и контакты — только после согласия.' },
]

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-paper">
      <PublicHeader />

      <main id="main">
        <section className="mx-auto max-w-page px-4 pb-6 pt-12 sm:px-6 lg:pt-16">
          <div className="grid items-end gap-10 lg:grid-cols-[1fr_1.1fr]">
            <div>
              <p className="text-sm text-ink-2">Федерация спортивного программирования, ЛЦТ 2026</p>
              <h1 className="mt-5 font-display font-bold leading-[1.08] tracking-[-0.03em] text-ink [font-size:clamp(2rem,4.2vw,3.25rem)]">
                Приглашайте разработчиков по&nbsp;результату, а&nbsp;не по&nbsp;резюме
              </h1>
              <p className="mt-6 max-w-[52ch] text-lg text-ink-2">
                Кандидат проходит адаптивный тест и подтверждает достижения на соревнованиях ФСП. Работодатель видит
                категорию и объяснение подборки, а потом сам приглашает — сразу с зарплатной вилкой.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to="/register?role=employer" className="btn-primary px-6 py-3 text-base">Найти кандидата</Link>
                <Link to="/register" className="btn-secondary px-6 py-3 text-base">Я ищу работу</Link>
              </div>
              <p className="mt-5 text-xs text-ink-3">
                Демо-вход: <Link to="/login?role=employer" className="text-accent hover:underline">hr@sibcode.demo</Link> или{' '}
                <Link to="/login" className="text-accent hover:underline">fsp001@demo.talent</Link>, пароль demo12345.
              </p>
            </div>
            <figure>
              <RussiaNetwork className="h-auto w-full" />
              <figcaption className="mt-3 flex flex-wrap justify-between gap-2 border-t border-line-strong pt-3 font-display text-xs text-ink-2">
                <span>89 региональных отделений ФСП</span>
                <span>один протокол, одни правила категории</span>
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="mx-auto max-w-page px-4 py-14 sm:px-6">
          <div className="grid items-start gap-10 lg:grid-cols-[1fr_1.15fr]">
            <div className="lg:pt-4">
              <h2 className="font-display text-2xl font-bold tracking-tight text-ink">Подборка читается как протокол</h2>
              <p className="mt-3 max-w-[48ch] text-ink-2">
                Место, категория «специализация × грейд», подтверждения и один скор. У каждого фактора своя полоса,
                а под карточкой — почему человек в выдаче и чего ему не хватает.
              </p>
              <dl className="mt-6 space-y-4 text-sm">
                <div><dt className="font-medium text-ink">Грейд подтверждает тест</dt><dd className="mt-0.5 text-ink-2">Заявленный грейд помечен отдельно и весит меньше.</dd></div>
                <div><dt className="font-medium text-ink">Результаты ФСП — отдельная ось</dt><dd className="mt-0.5 text-ink-2">Нет истории соревнований — ось выключается и не штрафует.</dd></div>
                <div><dt className="font-medium text-ink">Имя и регион не влияют на скор</dt><dd className="mt-0.5 text-ink-2">Карточка анонимна до согласия кандидата.</dd></div>
              </dl>
            </div>
            <ProtocolPreview />
          </div>
        </section>

        <section className="border-y border-line bg-panel">
          <div className="mx-auto grid max-w-page gap-12 px-4 py-14 sm:px-6 md:grid-cols-2">
            <Lane title="Кандидату" steps={CANDIDATE_STEPS} />
            <Lane title="Работодателю" steps={EMPLOYER_STEPS} />
          </div>
        </section>

        <section className="mx-auto max-w-page px-4 py-14 sm:px-6">
          <h2 className="font-display text-2xl font-bold tracking-tight text-ink">Почему категории можно верить</h2>
          <div className="mt-8 grid gap-8 md:grid-cols-3">
            {TRUST.map(({ Icon, title, text }) => (
              <div key={title}>
                <Icon className="text-accent" size={22} aria-hidden />
                <h3 className="mt-3 font-medium text-ink">{title}</h3>
                <p className="mt-1.5 text-sm text-ink-2">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-[#1B1C21] text-[#EDEDED]">
          <div className="mx-auto flex max-w-page flex-wrap items-center justify-between gap-6 px-4 py-12 sm:px-6">
            <div>
              <h2 className="font-display text-2xl font-bold">Опишите, кого ищете</h2>
              <p className="mt-2 text-sm text-[#C8C9CA]">Подборка с объяснением появится сразу после сохранения потребности.</p>
            </div>
            <Link to="/register?role=employer" className="btn bg-[#402FFF] px-6 py-3 text-white hover:bg-[#5444FF]">Создать аккаунт работодателя</Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
