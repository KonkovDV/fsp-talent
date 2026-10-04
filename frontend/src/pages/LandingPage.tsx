import { Link } from 'react-router-dom'
import { Code2, Shield, Trophy, Zap, ArrowRight, Medal, Lock, CheckCircle2 } from 'lucide-react'
import { useEffect, useState } from 'react'

/** ФСП diamond logo — standalone for landing */
function FspLogoFull() {
  return (
    <div className="flex items-center gap-3 select-none">
      <div
        style={{
          width: 40, height: 40,
          background: 'linear-gradient(135deg, #D42330, #FF4D5A)',
          clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <span style={{ color: '#fff', fontWeight: 900, fontSize: 16 }}>Ф</span>
      </div>
      <div className="flex flex-col" style={{ lineHeight: 1 }}>
        <span style={{ color: '#fff', fontWeight: 900, fontSize: 18, letterSpacing: '0.04em', fontFamily: 'Montserrat, Inter, sans-serif' }}>ФСП</span>
        <span style={{ color: 'rgba(255,255,255,0.55)', fontWeight: 500, fontSize: 10, letterSpacing: '0.12em' }}>ТАЛАНТ</span>
      </div>
    </div>
  )
}

const STATS = [
  { value: '5', label: 'дисциплин ФСП' },
  { value: '2', label: 'оси оценки' },
  { value: 'W3C VC', label: 'подпись результатов' },
  { value: '152-ФЗ', label: 'контакты по согласию' },
]

const FEATURES = [
  {
    Icon: Trophy,
    title: 'Двуосная оценка',
    desc: 'Грейд по опыту + уровень ФСП: процентиль, лестница ЕВСК и нижняя граница Байеса — не просто место в протоколе',
    accent: '#F0A500',
    bg: 'rgba(240,165,0,0.08)',
    border: 'rgba(240,165,0,0.25)',
  },
  {
    Icon: Lock,
    title: 'Анонимный поиск',
    desc: 'Навыки, разряд-эквивалент и причина попадания в выдачу. Имя и контакты — только после согласия кандидата',
    accent: '#1D82F5',
    bg: 'rgba(29,130,245,0.08)',
    border: 'rgba(29,130,245,0.25)',
  },
  {
    Icon: Shield,
    title: 'Проверяемая подпись',
    desc: 'Результат подписан криптографически. W3C VC 2.0, eddsa-jcs-2022 — подмена места ломает проверку',
    accent: '#22C55E',
    bg: 'rgba(34,197,94,0.08)',
    border: 'rgba(34,197,94,0.25)',
  },
  {
    Icon: Code2,
    title: '5 дисциплин',
    desc: 'Алгоритмика, продукт, безопасность, БАС, робототехника. Каждая — отдельный байесовский скор с нижней границей',
    accent: '#D42330',
    bg: 'rgba(212,35,48,0.08)',
    border: 'rgba(212,35,48,0.25)',
  },
]

const HOW = [
  { n: '01', title: 'Регистрация', desc: 'Участник привязывает ID ФСП. Работодатель создаёт аккаунт компании.' },
  { n: '02', title: 'Поиск', desc: 'Работодатель ищет по навыкам, грейду, дисциплине. Результаты анонимны.' },
  { n: '03', title: 'Оффер', desc: 'Оффер отправляется кандидату. Он принимает или отклоняет.' },
  { n: '04', title: 'Контакт', desc: 'Только после согласия кандидата открываются имя и контакты.' },
]

export default function LandingPage() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  return (
    <div className="min-h-dvh bg-surface-0 text-text-primary">

      {/* ══ NAV ══════════════════════════════════════════════ */}
      <header className="fsp-nav sticky top-0 z-40" role="banner">
        <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between" aria-label="Главная навигация">
          <a href="/" aria-label="ФСП Талант — главная">
            <FspLogoFull />
          </a>
          <div className="flex items-center gap-2">
            <Link to="/leaderboard" className="btn-nav text-sm">Лидерборд</Link>
            <Link to="/login"       className="btn-nav text-sm">Войти</Link>
            <Link to="/register"
              className="ml-1 btn-danger text-sm"
            >
              Регистрация <ArrowRight size={13} />
            </Link>
          </div>
        </nav>
        <div style={{ height: 2, background: 'linear-gradient(90deg, #D42330, #FF4D5A, #D42330)' }} aria-hidden />
      </header>

      {/* ══ HERO ═════════════════════════════════════════════ */}
      <section
        style={{ background: 'linear-gradient(150deg, #0A1F5C 0%, #1B3FA0 60%, #1555A0 100%)', position: 'relative', overflow: 'hidden' }}
        className="pt-24 pb-32 px-6 text-center"
        aria-labelledby="hero-heading"
      >
        {/* Grid pattern */}
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-30" aria-hidden />
        {/* Glow */}
        <div
          className="pointer-events-none absolute"
          style={{ top: -120, left: '50%', transform: 'translateX(-50%)', width: 800, height: 400, background: 'radial-gradient(ellipse, rgba(29,130,245,0.25), transparent 70%)', zIndex: 0 }}
          aria-hidden
        />

        <div
          className={`relative z-10 max-w-4xl mx-auto space-y-7 transition-all duration-700 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
          }`}
        >
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-bold"
            style={{ background: 'rgba(212,35,48,0.2)', border: '1px solid rgba(212,35,48,0.5)', color: '#FF6B75' }}>
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="animate-ping absolute h-full w-full rounded-full opacity-75" style={{ background: '#D42330' }} />
              <span className="relative rounded-full h-2 w-2" style={{ background: '#FF4D5A' }} />
            </span>
            LCT-2026 · Платформа открыта
          </div>

          {/* Headline */}
          <h1
            id="hero-heading"
            className="text-5xl text-balance animate-fade-up"
            style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900, color: '#FFFFFF', lineHeight: 1.1, animationDelay: '0.1s' }}
          >
            Маркетплейс{' '}
            <span className="text-gradient-fsp">ИТ-талантов</span>{' '}
            <span style={{ color: '#D42330' }}>России</span>
          </h1>

          <p
            className="text-lg text-balance animate-fade-up"
            style={{ color: 'rgba(255,255,255,0.75)', maxWidth: 640, margin: '0 auto', animationDelay: '0.2s' }}
          >
            Работодатель находит участников по протоколам ФСП и отправляет оффер.{' '}
            <strong style={{ color: '#fff', fontWeight: 700 }}>Имя и контакты открываются только после согласия кандидата</strong>.
          </p>

          {/* CTA */}
          <div
            className="flex flex-col sm:flex-row gap-3 justify-center animate-fade-up"
            style={{ animationDelay: '0.3s' }}
          >
            <Link to="/register?role=participant"
              className="btn-danger text-base px-8 py-3 rounded-md font-bold"
            >
              Я участник ФСП <Medal size={16} />
            </Link>
            <Link to="/register?role=employer"
              className="btn-secondary-white text-base px-8 py-3 rounded-md font-bold"
            >
              Я работодатель
            </Link>
          </div>

          {/* Trust badges */}
          <div className="flex flex-wrap items-center justify-center gap-4 animate-fade-up" style={{ animationDelay: '0.4s' }}>
            {['Официальные данные ФСП', '152-ФЗ соответствие', 'W3C VC 2.0'].map(t => (
              <span key={t} className="flex items-center gap-1.5 text-sm" style={{ color: 'rgba(255,255,255,0.6)' }}>
                <CheckCircle2 size={13} style={{ color: '#22C55E' }} />
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* Diagonal cut */}
        <div
          className="pointer-events-none absolute bottom-0 left-0 right-0"
          style={{ height: 60, background: 'oklch(var(--surface-0))', clipPath: 'polygon(0 100%, 100% 100%, 100% 0)' }}
          aria-hidden
        />
      </section>

      {/* ══ STATS BAR ════════════════════════════════════════ */}
      <section className="border-y border-border py-10" aria-label="Статистика платформы">
        <div className="max-w-7xl mx-auto px-6">
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {STATS.map(s => (
              <div key={s.label} className="text-center">
                <dt
                  className="text-3xl tabular mb-1"
                  style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900, background: 'linear-gradient(135deg, #1D82F5, #5BADFF)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
                >
                  {s.value}
                </dt>
                <dd className="text-xs text-text-muted uppercase tracking-widest font-semibold">{s.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* ══ FEATURES ═════════════════════════════════════════ */}
      <section className="py-24 px-6" aria-labelledby="features-heading">
        <div className="max-w-7xl mx-auto">
          <h2
            id="features-heading"
            className="text-3xl text-center mb-14 text-balance"
            style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900 }}
          >
            Возможности платформы
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FEATURES.map(({ Icon, title, desc, accent, bg, border }) => (
              <div
                key={title}
                className="card-hover space-y-4"
                style={{ borderLeft: `3px solid ${accent}` }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: bg, border: `1px solid ${border}` }}
                >
                  <Icon size={20} style={{ color: accent }} />
                </div>
                <h3 className="font-bold text-text-primary">{title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ HOW IT WORKS ═════════════════════════════════════ */}
      <section
        className="py-24 px-6"
        style={{ background: 'linear-gradient(180deg, oklch(var(--surface-1)) 0%, oklch(var(--surface-0)) 100%)' }}
        aria-labelledby="how-heading"
      >
        <div className="max-w-5xl mx-auto">
          <h2
            id="how-heading"
            className="text-3xl text-center mb-14 text-balance"
            style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900 }}
          >
            Как это работает
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {HOW.map(({ n, title, desc }) => (
              <div key={n} className="card-fsp space-y-3">
                <span
                  className="text-4xl tabular"
                  style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900, background: 'linear-gradient(135deg, #1B3FA0, #1D82F5)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
                >
                  {n}
                </span>
                <h3 className="font-bold text-text-primary">{title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══ CTA ══════════════════════════════════════════════ */}
      <section
        className="py-20 px-6 text-center"
        style={{ background: 'linear-gradient(135deg, #0A1F5C, #1B3FA0)' }}
      >
        <div className="max-w-lg mx-auto space-y-6">
          <h2 className="text-2xl text-white" style={{ fontFamily: 'Montserrat, Inter, sans-serif', fontWeight: 900 }}>
            Готовы начать?
          </h2>
          <p style={{ color: 'rgba(255,255,255,0.7)' }}>Регистрация бесплатна. Анонимность гарантирована до оффера.</p>
          <Link to="/register?role=participant" className="btn-danger px-8 py-3 inline-flex text-base font-bold">
            Зарегистрироваться
          </Link>
        </div>
      </section>

      {/* ══ FOOTER ═══════════════════════════════════════════ */}
      <footer style={{ background: '#06133A', borderTop: '1px solid rgba(255,255,255,0.1)' }} className="py-8" role="contentinfo">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <FspLogoFull />
          <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>
            &copy; 2026 Федерация спортивного программирования · прототип · 152-ФЗ
          </p>
          <div className="flex items-center gap-5">
            {[['Лидерборд', '/leaderboard'], ['Войти', '/login'], ['Регистрация', '/register']].map(([label, to]) => (
              <Link
                key={to}
                to={to}
                style={{ color: 'rgba(255,255,255,0.45)', fontSize: 13 }}
                className="hover:text-white transition-colors"
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      </footer>
    </div>
  )
}
