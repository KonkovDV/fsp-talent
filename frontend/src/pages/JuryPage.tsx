import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Building2, FileCheck2, UserRound } from 'lucide-react'
import { apiError, categoryRanking, telegramAchievements, telegramVacancies } from '../api/client'
import { GRADES, ROLE_RU, gradeRu } from '../labels'
import PublicShell from '../components/PublicShell'
import { PageHeader } from '../components/ui'

/** A three-minute route through the product, in the order a jury member would click it. */
const ROUTE = [
  { who: 'Работодатель', what: 'Потребности → «Backend на Python в платёжный сервис»', see: 'Где искать: рекомендованные категории. Подборка по одной оценке соответствия с полосами факторов и «Почему в выдаче».' },
  { who: 'Работодатель', what: 'Отметить трёх кандидатов «Сравнить», открыть вкладку «Как проверим»', see: 'Факторы рядом, без имён. Доли тем из текста потребности и примеры заданий.' },
  { who: 'Работодатель', what: '«Пригласить»: должность, вилка до вычета НДФЛ, способ связи', see: 'Без вилки приглашение не отправить. Кандидат получает уведомление и письмо.' },
  { who: 'Кандидат', what: 'Приглашения → «Принять и открыть контакты» → «Переписка»', see: 'Компания и вилка видны до решения. У работодателя открываются контакты, в журнале доступа — запись.' },
  { who: 'Без аккаунта', what: '«Как устроен тест» и «Проверка удостоверения»', see: 'Методика теста и проверка подписи результатов ФСП третьей стороной.' },
]

/** Three ways in for a jury: two demo accounts and the public pages. No third login. */
export default function JuryPage() {
  const [fspId, setFspId] = useState('FSP001')
  const [note, setNote] = useState('')
  const [rankRole, setRankRole] = useState('backend')
  const [rankGrade, setRankGrade] = useState('middle')
  const [ranks, setRanks] = useState<{ place: number; test: number }[] | null>(null)
  const [busy, setBusy] = useState(false)
  const show = async (kind: 'achievements' | 'vacancies') => {
    setBusy(true)
    setNote('')
    try {
      const response = kind === 'achievements' ? await telegramAchievements(fspId) : await telegramVacancies()
      setNote(response.data.text as string)
    } catch (error) {
      setNote(apiError(error, 'Запрос не выполнился'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <PublicShell>
      <PageHeader
        title="Режим жюри"
        lead="Отдельного входа для жюри нет. Кандидат и работодатель — демо-аккаунты, пароль demo12345. Публичные страницы открываются без аккаунта."
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
          <p className="mt-2 text-sm text-ink-2">Методика теста и проверка удостоверения. Это третья сторона просмотра.</p>
          <div className="mt-auto flex flex-col items-start gap-1 pt-3">
            <Link to="/method" className="link inline-flex min-h-8 items-center text-sm">Как устроен тест</Link>
            <Link to="/badge" className="link inline-flex min-h-8 items-center text-sm">Проверка удостоверения</Link>
            <Link to="/evaluate" className="link inline-flex min-h-8 items-center text-sm">Подбор на своей разметке</Link>
          </div>
        </section>
      </div>

      <section className="mt-10" aria-labelledby="route-title">
        <h2 id="route-title" className="font-display text-xl font-bold tracking-[-0.02em] text-ink">Маршрут на три минуты</h2>
        <ol className="mt-5 overflow-hidden rounded-xl border border-line-strong/70 bg-panel shadow-xs dark:border-line">
          {ROUTE.map((r, i) => (
            <li key={r.what} className="grid gap-x-4 gap-y-1 border-b border-line px-4 py-4 last:border-b-0 sm:grid-cols-[2.5rem_9rem_1fr_1.2fr] sm:items-baseline sm:px-5">
              <span className="place text-accent">{i + 1}</span>
              <span className="text-xs font-medium text-ink-3 sm:text-sm">{r.who}</span>
              <span className="font-medium text-ink">{r.what}</span>
              <span className="text-sm text-ink-2">{r.see}</span>
            </li>
          ))}
        </ol>
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
        {note && <pre className="whitespace-pre-wrap text-sm text-ink-2" role="status">{note}</pre>}
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
            void categoryRanking(rankRole, rankGrade).then(r => setRanks(r.data.items)).catch(error => setNote(apiError(error, 'Порядок не открылся'))).finally(() => setBusy(false))
          }}>Показать порядок</button>
        </div>
        {ranks && (ranks.length === 0
          ? <p className="text-sm text-ink-2">В этой категории подтверждённых тестом нет.</p>
          : <ol className="text-sm text-ink">{ranks.map(row => <li key={row.place}>{row.place}. тест {Math.round(row.test * 100)} %</li>)}</ol>)}
      </section>

      <p className="mt-6 text-sm text-ink-2">
        Набор этих профилей в JSON и CSV проверяется при запуске стенда и в базу не записывается.
      </p>
    </PublicShell>
  )
}
