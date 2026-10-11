import { type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, FileCheck2, UserRound } from 'lucide-react'
import { apiError, askPublicGuide, categoryRanking, telegramAchievements, telegramVacancies } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'
import PublicShell from '../components/PublicShell'
import Term from '../components/Term'
import { PageHeader } from '../components/ui'

const PATHS: {
  title: string
  who: string
  to: string
  steps: { go: string; see: ReactNode; to: string }[]
}[] = [
  {
    title: 'Работодатель',
    who: 'hr@sibcode.demo',
    to: '/login?role=employer&next=/employer/needs',
    steps: [
      { go: 'Потребности', to: '/login?role=employer&next=/employer/needs', see: 'Текст или одна открытая ссылка заполняют черновик. Сохранение — только кнопкой «Создать». Опасные формулировки подписываются, потребность остаётся.' },
      { go: 'Подборка', to: '/login?role=employer&next=/employer/needs', see: 'Имени нет. На карточке разложен балл и отдельно ось ФСП: нижняя граница в порядке, разброс — среднее ± неопределённость.' },
      { go: 'Поиск по банку', to: '/login?role=employer&next=/employer/search', see: 'Фильтры по специализации, грейду, навыкам и ФСП. Ячейка банка открывает тот же поиск.' },
      { go: 'Пригласить', to: '/login?role=employer&next=/employer/offers', see: 'Без вилки до НДФЛ отправить нельзя. Рядом сумма на руки. Балл компании виден до согласия кандидата.' },
      { go: 'Приглашения', to: '/login?role=employer&next=/employer/offers', see: 'Практика и черновик кода на собеседовании. Ни то ни другое грейд не меняет.' },
    ],
  },
  {
    title: 'Кандидат',
    who: 'fsp001@demo.talent',
    to: '/login?next=/candidate/assessment',
    steps: [
      { go: 'Опрос', to: '/login?next=/candidate', see: 'Специализация и заявленный грейд. Без опроса тест не стартует.' },
      { go: 'Тест на грейд', to: '/login?next=/candidate/assessment', see: 'Полный тест подтверждает выбранный уровень. Пробный (экспресс) — 15 заданий за 5 минут: грейд не ставит и в поиске не учитывается. Отдельные попытки: jury1@demo.talent … jury10@demo.talent.' },
      { go: 'Категория и результаты', to: '/login?next=/candidate/results', see: 'Подтверждённый грейд и протоколы ФСП. Это не грейд и не цифровой след.' },
      { go: 'Приглашения', to: '/login?next=/candidate/offers', see: 'Компания и вилка видны сразу. Имя и контакты — после «Принять». После жалобы вакансия остаётся в поиске до проверки.' },
      { go: 'Отклик на вакансию', to: '/login?next=/candidate/vacancies', see: 'Открытые вакансии с вилкой. Отклик раскрывает контакты так же, как принятие приглашения.' },
    ],
  },
  {
    title: 'Без аккаунта',
    who: 'третья сторона',
    to: '/method',
    steps: [
      { go: 'Как устроен тест', to: '/method', see: <>Порог уровня, самые полезные задания у порога, <Term term="метод Симпсона–Хеттера">ограничение частоты показа одного задания</Term>, карантин утёкших заданий. Страница грейд не ставит.</> },
      { go: 'Проверка удостоверения', to: '/badge', see: <>Электронная подпись по стандарту W3C и QR-код с <Term term="did:web — адрес ключа издателя на его домене">адресом ключа издателя</Term>. Имени в краткой карточке нет.</> },
      { go: 'Подбор на своей разметке', to: '/evaluate', see: <><Term term="nDCG@10">Качество порядка выдачи</Term>, <Term term="P@10">доля подходящих в первой десятке</Term> и <Term term="MAP">средняя точность</Term>. Пары не сохраняются, банк не читается.</> },
      { go: 'Рейтинг', to: '/leaderboard', see: 'Публичный список без имени.' },
    ],
  },
]

const SCENARIO_33: { n: number; title: string; to: string; see: string }[] = [
  { n: 1, title: 'Вход кандидата', to: '/login?next=/candidate', see: 'Демо fsp001@demo.talent или свободный jury1…10, пароль demo12345.' },
  { n: 2, title: 'Опрос', to: '/login?next=/candidate', see: 'Специализация и заявленный грейд в кабинете кандидата.' },
  { n: 3, title: 'Тест', to: '/login?next=/candidate/assessment', see: 'Полный тест ставит грейд. Пробный экспресс — только знакомство с заданиями, грейд не подтверждает.' },
  { n: 4, title: 'Категория', to: '/login?next=/candidate/results', see: 'Подтверждённый грейд и категория, видимые работодателю.' },
  { n: 5, title: 'Поиск работодателем', to: '/login?role=employer&next=/employer/search', see: 'Банк и фильтры; подборка из потребности с объяснением «почему в выдаче».' },
  { n: 6, title: 'Приглашение', to: '/login?role=employer&next=/employer/offers', see: 'Вилка до НДФЛ и способ связи обязательны.' },
  { n: 7, title: 'Принятие и контакты', to: '/login?next=/candidate/offers', see: 'Кандидат принимает — работодатель видит контакты.' },
  { n: 8, title: 'Отклик на вакансию', to: '/login?next=/candidate/vacancies', see: 'Дополнительный путь: кандидат откликается сам, контакты открываются так же.' },
]

const SCENARIO_KEY = 'fsp-jury-scenario-33'

const PUBLIC_GUIDE = new Set(['/method', '/badge', '/jury', '/evaluate', '/leaderboard'])

/** Three ways in for a jury: two demo accounts and the public pages. No third login. */
export default function JuryPage() {
  const [fspId, setFspId] = useState('FSP001')
  const [channel, setChannel] = useState('')
  const [channelError, setChannelError] = useState('')
  const [rankRole, setRankRole] = useState('backend')
  const [rankGrade, setRankGrade] = useState('middle')
  const [ranks, setRanks] = useState<{ place: number; test: number }[] | null>(null)
  const [rankHidden, setRankHidden] = useState(0)
  const [rankError, setRankError] = useState('')
  const [busy, setBusy] = useState(false)
  const [question, setQuestion] = useState('')
  const [guideError, setGuideError] = useState('')
  const [hint, setHint] = useState<{ answer: string; links: { label: string; to: string }[] } | null>(null)
  const [scenarioTick, setScenarioTick] = useState(0)
  useEffect(() => {
    const bump = () => setScenarioTick(n => n + 1)
    window.addEventListener('storage', bump)
    window.addEventListener('fsp-jury-scenario', bump)
    return () => {
      window.removeEventListener('storage', bump)
      window.removeEventListener('fsp-jury-scenario', bump)
    }
  }, [])
  const show = async (kind: 'achievements' | 'vacancies') => {
    setBusy(true)
    setChannel('')
    setChannelError('')
    try {
      const response = kind === 'achievements' ? await telegramAchievements(fspId) : await telegramVacancies()
      setChannel(response.data.text as string)
    } catch (error) {
      setChannelError(apiError(error, 'Запрос не выполнился'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <PublicShell>
      <PageHeader
        title="Режим жюри"
        lead="Отдельного входа для жюри нет. Пароль демо-аккаунтов demo12345. Демо-доступ для жюри: данные синтетические. Публичные страницы открываются без аккаунта."
      />
      <div className="grid gap-4 md:grid-cols-3">
        <section className="card flex flex-col">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink"><UserRound size={18} className="text-accent" aria-hidden />Кандидат</h2>
          <p className="mt-2 text-sm text-ink-2">Профиль с историей ФСП, тест и приглашения.</p>
          <p className="mt-3 rounded-md bg-sunken px-3 py-2 font-mono text-sm text-ink">fsp001@demo.talent</p>
          <p className="mt-2 text-xs text-ink-3">Демо-доступ для жюри: данные синтетические</p>
          <p className="mt-2 text-xs text-ink-3">Для теста на грейд: jury1@demo.talent … jury10@demo.talent, у каждого свои попытки.</p>
          <div className="mt-auto pt-4"><Link to="/login" className="btn-primary">Войти как кандидат</Link></div>
        </section>
        <section className="card flex flex-col">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink"><Building2 size={18} className="text-invite" aria-hidden />Работодатель</h2>
          <p className="mt-2 text-sm text-ink-2">Компания «Сибирский код»: потребности, подборка, задания.</p>
          <p className="mt-3 rounded-md bg-sunken px-3 py-2 font-mono text-sm text-ink">hr@sibcode.demo</p>
          <p className="mt-2 text-xs text-ink-3">Демо-доступ для жюри: данные синтетические</p>
          <div className="mt-auto pt-4"><Link to="/login?role=employer" className="btn-primary">Войти как работодатель</Link></div>
        </section>
        <section className="card flex flex-col">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink"><FileCheck2 size={18} className="text-ink-2" aria-hidden />Без аккаунта</h2>
          <p className="mt-2 text-sm text-ink-2">Методика, подпись удостоверения и своя разметка подбора.</p>
          <div className="mt-auto flex flex-col items-start gap-1 pt-3">
            <Link to="/method" className="link inline-flex min-h-8 items-center text-sm">Как устроен тест</Link>
            <Link to="/badge" className="link inline-flex min-h-8 items-center text-sm">Проверка удостоверения</Link>
            <Link to="/evaluate" className="link inline-flex min-h-8 items-center text-sm">Подбор на своей разметке</Link>
            <Link to="/leaderboard" className="link inline-flex min-h-8 items-center text-sm">Рейтинг</Link>
          </div>
        </section>
      </div>


      <section className="mt-10" aria-labelledby="scenario-title" data-testid="jury-scenario-33">
        <h2 id="scenario-title" className="font-display text-xl font-bold tracking-[-0.02em] text-ink">Сквозной сценарий ТЗ 3.3</h2>
        <p className="mt-2 max-w-3xl text-sm text-ink-2">
          Восемь шагов без пояснений снаружи. Отметка «готово» хранится только в этом браузере.
          Пробный экспресс-тест грейд не ставит — для категории нужен полный тест.
        </p>
        <ol className="mt-5 grid gap-3 sm:grid-cols-2">
          {SCENARIO_33.map(step => {
            void scenarioTick
            const done = typeof window !== 'undefined' && window.localStorage.getItem(`${SCENARIO_KEY}:${step.n}`) === '1'
            return (
              <li key={step.n} className="card flex flex-col p-4">
                <p className="font-display text-sm font-bold text-ink">
                  <span className="text-ink-3">{step.n}. </span>{step.title}
                  {done && <span className="ml-2 text-xs font-medium text-ok">готово</span>}
                </p>
                <p className="mt-1 flex-1 text-sm text-ink-2">{step.see}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Link to={step.to} className="btn-secondary btn-sm">Открыть</Link>
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    data-testid={`scenario-done-${step.n}`}
                    onClick={() => {
                      const key = `${SCENARIO_KEY}:${step.n}`
                      if (window.localStorage.getItem(key) === '1') window.localStorage.removeItem(key)
                      else window.localStorage.setItem(key, '1')
                      window.dispatchEvent(new Event('fsp-jury-scenario'))
                    }}
                  >
                    {done ? 'Снять отметку' : 'Готово'}
                  </button>
                </div>
              </li>
            )
          })}
        </ol>
      </section>

      <section className="mt-10" aria-labelledby="route-title">
        <h2 id="route-title" className="font-display text-xl font-bold tracking-[-0.02em] text-ink">Три пути</h2>
        <p className="mt-2 max-w-3xl text-sm text-ink-2">Один и тот же человек может пройти их по очереди. Пароль на экране входа подставляется кнопкой демо-аккаунта.</p>
        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {PATHS.map(path => (
            <article key={path.title} className="card flex flex-col p-5">
              <h3 className="font-display text-lg font-bold text-ink">{path.title}</h3>
              <p className="mt-1 font-mono text-xs text-ink-3">{path.who}</p>
              <ol className="mt-4 space-y-3">
                {path.steps.map((step, i) => (
                  <li key={step.go} className="text-sm">
                    <p className="font-medium text-ink"><span className="text-ink-3">{i + 1}. </span>{step.go}
                      {' '}
                      <Link to={step.to} className="text-accent hover:underline">Открыть</Link>
                    </p>
                    <p className="mt-0.5 text-ink-2">{step.see}</p>
                  </li>
                ))}
              </ol>
              <Link to={path.to} className="btn-secondary btn-sm mt-4 self-start">Открыть</Link>
            </article>
          ))}
        </div>
      </section>

      <section className="card mt-8" aria-labelledby="bounds-title">
        <h2 id="bounds-title" className="font-display text-lg font-bold text-ink">Что эти экраны не делают</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink-2">
          <li>Грейд ставит только тест выбранного уровня. Протокол, разряд, свидетельство и файл его не меняют и не понижают.</li>
          <li>Имя, аватар и контакты закрыты, пока кандидат не принял приглашение.</li>
          <li><Term term="LCB — нижняя граница доверительного интервала">Осторожная оценка ФСП</Term> (нижняя граница уровня) — отдельная ось порядка. Разброс на карточке — та же оценка, среднее ± неопределённость.</li>
          <li>Модель пары двигает только верхние 50 фактора «Запрос», и только если на сервере есть файл весов. <Term term="BM25">Поиск по ключевым словам</Term> в порядок списка не входит.</li>
        </ul>
      </section>

      <section className="card mt-8 space-y-3" aria-label="Канал без кабинета">
        <h2 className="font-display text-lg font-bold text-ink">Протоколы и вакансии без кабинета</h2>
        <p className="text-sm text-ink-2">Те же ответы может забрать мессенджер. Имени, почты и телефона в них нет. Грейд по протоколу не ставится.</p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="field-label" htmlFor="fsp-poke">ФСП ID</label>
            <input id="fsp-poke" className="input font-mono" value={fspId} onChange={e => setFspId(e.target.value)} aria-label="ФСП ID" />
          </div>
          <button type="button" className="btn-secondary" disabled={busy || fspId.trim().length < 4} onClick={() => { void show('achievements') }}>Протоколы</button>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => { void show('vacancies') }}>Вакансии</button>
        </div>
        {channelError && <p className="notice-error" role="alert">{channelError}</p>}
        {channel && <pre className="whitespace-pre-wrap text-sm text-ink-2" role="status">{channel}</pre>}
        <h2 className="font-display text-lg font-bold text-ink">Порядок внутри категории</h2>
        <p className="text-sm text-ink-2">Места по подтверждающему тесту. Имени и номера аккаунта в списке нет.</p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm text-ink-2">Специализация
            <select className="select mt-1" value={rankRole} onChange={e => setRankRole(e.target.value)} aria-label="Специализация для порядка">
              {Object.entries(ROLE_RU).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
            </select>
          </label>
          <label className="text-sm text-ink-2">Грейд
            <select className="select mt-1" value={rankGrade} onChange={e => setRankGrade(e.target.value)} aria-label="Грейд для порядка">
              {GRADES.map(code => <option key={code} value={code}>{gradeRu(code)}</option>)}
            </select>
          </label>
          <button type="button" className="btn-secondary" disabled={busy} onClick={() => {
            setBusy(true)
            setRankError('')
            void categoryRanking(rankRole, rankGrade)
              .then(r => { setRanks(r.data.items); setRankHidden(r.data.hidden ? r.data.min_cell ?? 5 : 0) })
              .catch(error => setRankError(apiError(error, 'Порядок не открылся')))
              .finally(() => setBusy(false))
          }}>Показать порядок</button>
        </div>
        {rankError && <p className="notice-error" role="alert">{rankError}</p>}
        {ranks && (ranks.length === 0
          ? <p className="text-sm text-ink-2" data-testid="rank-hidden">{rankHidden
            ? `Скрыто: в категории меньше ${rankHidden} участников с публичным профилем — защита персональных данных.`
            : 'В этой категории пока нет участников с подтверждённым тестом грейдом.'}</p>
          : <ol className="text-sm text-ink">{ranks.map(row => <li key={row.place}>{row.place}. тест {Math.round(row.test * 100)} %</li>)}</ol>)}
      </section>

      <form className="card mt-8 space-y-3 p-5" onSubmit={e => {
        e.preventDefault()
        setBusy(true)
        setGuideError('')
        void askPublicGuide(question.trim())
          .then(r => setHint(r.data))
          .catch(error => setGuideError(apiError(error, 'Подсказка не открылась')))
          .finally(() => setBusy(false))
      }}>
        <h2 className="font-display text-lg font-bold text-ink">Куда нажать без входа</h2>
        <p className="text-sm text-ink-2">Ответ — только публичная страница. Вопрос на сервере не хранится и в модель не уходит.</p>
        <input className="input" value={question} onChange={e => setQuestion(e.target.value)} maxLength={200} aria-label="Вопрос без входа" placeholder="Например, где проверить подпись" />
        <button type="submit" className="btn-secondary btn-sm" disabled={busy || question.trim().length < 2}>Показать страницу</button>
        {guideError && <p className="notice-error" role="alert">{guideError}</p>}
        {hint && (
          <div className="text-sm text-ink">
            <p>{hint.answer}</p>
            <ul className="mt-2 space-y-1">
              {hint.links.filter(link => PUBLIC_GUIDE.has(link.to)).map(link => (
                <li key={link.to}><Link to={link.to} className="text-accent hover:underline">{link.label}</Link></li>
              ))}
            </ul>
          </div>
        )}
      </form>

      <p className="mt-6 text-sm text-ink-2">
        Набор этих профилей в JSON и CSV проверяется при запуске стенда и в базу не записывается.
      </p>
    </PublicShell>
  )
}
