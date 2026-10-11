import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, FileCheck2, UserRound } from 'lucide-react'
import { apiError, askPublicGuide, categoryRanking, telegramAchievements, telegramVacancies } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'
import PublicShell from '../components/PublicShell'
import { PageHeader } from '../components/ui'

const PATHS: {
  title: string
  who: string
  to: string
  steps: { go: string; see: string }[]
}[] = [
  {
    title: 'Работодатель',
    who: 'hr@sibcode.demo',
    to: '/login?role=employer',
    steps: [
      { go: 'Потребности', see: 'Текст или одна открытая ссылка заполняют черновик. Сохранение — только кнопкой «Создать». Опасные формулировки подписываются, потребность остаётся.' },
      { go: 'Подборка', see: 'Имени нет. На карточке разложен балл и отдельно ось ФСП: нижняя граница в порядке, разброс — среднее ± неопределённость.' },
      { go: 'Сравнить и «Как проверим»', see: 'До четырёх карточек рядом. Доли тем из текста и примеры заданий без ответа. Грейд этот тест не ставит.' },
      { go: 'Пригласить', see: 'Без вилки до НДФЛ отправить нельзя. Рядом сумма на руки. Балл компании виден до согласия кандидата.' },
      { go: 'Приглашения', see: 'Практика и черновик кода на собеседовании. Ни то ни другое грейд не меняет.' },
    ],
  },
  {
    title: 'Кандидат',
    who: 'fsp001@demo.talent',
    to: '/login',
    steps: [
      { go: 'Тест на грейд', see: 'Подтверждается только выбранный уровень. Для отдельных попыток: jury1@demo.talent … jury10@demo.talent.' },
      { go: 'Результаты ФСП', see: 'Протокол и файл. Это не грейд и не цифровой след. Разряд — справка.' },
      { go: 'Профиль', see: 'Свидетельство добавляет цитату к навыку. Логин кода до согласия скрыт.' },
      { go: 'Приглашения', see: 'Компания и вилка видны сразу. Имя и контакты — после «Принять». Жалоба вакансию не закрывает.' },
    ],
  },
  {
    title: 'Без аккаунта',
    who: 'третья сторона',
    to: '/method',
    steps: [
      { go: 'Как устроен тест', see: 'Порог, информация у порога, Симпсон–Хеттер, карантин. Страница грейд не ставит.' },
      { go: 'Проверка удостоверения', see: 'Подпись W3C и QR документа did:web. Имени в краткой карточке нет.' },
      { go: 'Подбор на своей разметке', see: 'nDCG, P@10 и MAP. Пары не сохраняются, банк не читается.' },
      { go: 'Рейтинг', see: 'Публичный список без имени.' },
    ],
  },
]

const PUBLIC_GUIDE = new Set(['/method', '/badge', '/jury', '/evaluate', '/leaderboard'])

/** Three ways in for a jury: two demo accounts and the public pages. No third login. */
export default function JuryPage() {
  const [fspId, setFspId] = useState('FSP001')
  const [channel, setChannel] = useState('')
  const [channelError, setChannelError] = useState('')
  const [rankRole, setRankRole] = useState('backend')
  const [rankGrade, setRankGrade] = useState('middle')
  const [ranks, setRanks] = useState<{ place: number; test: number }[] | null>(null)
  const [rankError, setRankError] = useState('')
  const [busy, setBusy] = useState(false)
  const [question, setQuestion] = useState('')
  const [guideError, setGuideError] = useState('')
  const [hint, setHint] = useState<{ answer: string; links: { label: string; to: string }[] } | null>(null)
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
        lead="Отдельного входа для жюри нет. Пароль демо-аккаунтов demo12345. Публичные страницы открываются без аккаунта."
      />
      <div className="grid gap-4 md:grid-cols-3">
        <section className="card flex flex-col">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink"><UserRound size={18} className="text-accent" aria-hidden />Кандидат</h2>
          <p className="mt-2 text-sm text-ink-2">Профиль с историей ФСП, тест и приглашения.</p>
          <p className="mt-3 rounded-md bg-sunken px-3 py-2 font-mono text-sm text-ink">fsp001@demo.talent</p>
          <p className="mt-2 text-xs text-ink-3">Для теста на грейд: jury1@demo.talent … jury10@demo.talent, у каждого свои попытки.</p>
          <div className="mt-auto pt-4"><Link to="/login" className="btn-primary">Войти как кандидат</Link></div>
        </section>
        <section className="card flex flex-col">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink"><Building2 size={18} className="text-invite" aria-hidden />Работодатель</h2>
          <p className="mt-2 text-sm text-ink-2">Компания «Сибирский код»: потребности, подборка, задания.</p>
          <p className="mt-3 rounded-md bg-sunken px-3 py-2 font-mono text-sm text-ink">hr@sibcode.demo</p>
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

      <section className="mt-10" aria-labelledby="route-title">
        <h2 id="route-title" className="font-display text-xl font-bold tracking-[-0.02em] text-ink">Три пути</h2>
        <p className="mt-2 max-w-3xl text-sm text-ink-2">Один и тот же человек может пройти их по очереди. Пароль на экране входа подставляется кнопкой демо-аккаунта.</p>
        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {PATHS.map(path => (
            <article key={path.title} className="card flex flex-col p-5">
              <h3 className="font-display text-lg font-bold text-ink">{path.title}</h3>
              <p className="mt-1 font-mono text-xs text-ink-3">{path.who}</p>
              <ol className="mt-4 space-y-3">
                {path.steps.map((step, index) => (
                  <li key={step.go} className="grid grid-cols-[1.5rem_1fr] gap-2 text-sm">
                    <span className="place text-accent">{index + 1}</span>
                    <span>
                      <span className="font-medium text-ink">{step.go}.</span>{' '}
                      <span className="text-ink-2">{step.see}</span>
                    </span>
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
          <li>Нижняя граница ФСП — отдельная ось порядка. Разброс на карточке — та же оценка, среднее ± неопределённость.</li>
          <li>Модель пары двигает только верхние 50 фактора «Запрос», и только если на сервере есть файл весов. Формула BM25 в порядок списка не входит.</li>
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
              .then(r => setRanks(r.data.items))
              .catch(error => setRankError(apiError(error, 'Порядок не открылся')))
              .finally(() => setBusy(false))
          }}>Показать порядок</button>
        </div>
        {rankError && <p className="notice-error" role="alert">{rankError}</p>}
        {ranks && (ranks.length === 0
          ? <p className="text-sm text-ink-2" data-testid="rank-hidden">Меньше 5 публичных профилей — скрыто (k-анонимность: по малой группе можно узнать человека).</p>
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
