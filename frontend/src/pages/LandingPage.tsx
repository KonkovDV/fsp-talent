import { Link } from 'react-router-dom'
import { Code2, Shield, Trophy, Zap, Star, ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'

const STATS = [
  { value: '5', label: 'дисциплин ФСП' },
  { value: '2 оси', label: 'грейд и уровень' },
  { value: 'VC 2.0', label: 'подпись платформы' },
  { value: '152-ФЗ', label: 'контакты после согласия' },
]

const FEATURES = [
  {
    icon: Trophy,
    title: 'Две оси оценки',
    desc: 'Грейд по опыту + уровень ФСП: процентиль, лестница ЕВСК и нижняя граница Bayes — не просто место в протоколе',
    accent: 'text-yellow-400',
    bg: 'bg-yellow-500/10 border-yellow-500/20',
  },
  {
    icon: Zap,
    title: 'Анонимный поиск',
    desc: 'Навыки, разряд-эквивалент и причина попадания в выдачу. Имя и контакты — только после согласия кандидата',
    accent: 'text-cyan-400',
    bg: 'bg-cyan-500/10 border-cyan-500/20',
  },
  {
    icon: Shield,
    title: 'Проверяемая подпись',
    desc: 'Платформа подписывает результат из ФСП. W3C VC 2.0, eddsa-jcs-2022 — подмена места ломает проверку',
    accent: 'text-emerald-400',
    bg: 'bg-emerald-500/10 border-emerald-500/20',
  },
  {
    icon: Code2,
    title: '5 дисциплин',
    desc: 'Алгоритмика, продукт, безопасность, БАС, робототехника. Каждая — отдельный байесовский скор с нижней границей',
    accent: 'text-violet-400',
    bg: 'bg-violet-500/10 border-violet-500/20',
  },
]

export default function LandingPage() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => { setMounted(true) }, [])

  return (
    <div className="min-h-dvh bg-surface-0 text-text-primary">

      {/* Nav */}
      <header className="glass-nav sticky top-0 z-40" role="banner">
        <nav className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between" aria-label="Главная навигация">
          <a href="/" className="flex items-center gap-2" aria-label="FSP Talent — главная">
            <div className="w-7 h-7 rounded-lg bg-brand flex items-center justify-center text-white text-xs font-bold glow-brand">
              F
            </div>
            <span className="text-sm font-bold">FSP Talent</span>
          </a>
          <div className="flex items-center gap-2">
            <Link to="/leaderboard" className="btn-ghost text-sm">Лидерборд</Link>
            <Link to="/login"       className="btn-ghost text-sm">Войти</Link>
            <Link to="/register"    className="btn-primary text-sm">
              Регистрация <ArrowRight size={14}/>
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section
        className="relative overflow-hidden pt-24 pb-28 px-6 text-center"
        aria-labelledby="hero-heading"
      >
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-40" aria-hidden />
        <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(ellipse 80% 50% at 50% -10%, oklch(0.45 0.22 275 / 0.25), transparent)' }} aria-hidden />

        <div className={`max-w-4xl mx-auto space-y-6 transition-all duration-700 ${
          mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
        }`}>
          <div className="inline-flex items-center gap-2 badge-brand text-sm px-4 py-1.5 animate-fade-in">
            <span className="relative flex h-2 w-2" aria-hidden>
              <span className="animate-ping absolute h-full w-full rounded-full bg-brand opacity-75" />
              <span className="relative rounded-full h-2 w-2 bg-brand-bright" />
            </span>
            <Star size={13}/> LCT-2026 • Платформа открыта
          </div>

          <h1
            id="hero-heading"
            className="text-5xl font-bold leading-tight text-balance animate-fade-up"
            style={{ animationDelay: '0.1s' }}
          >
            Маркетплейс{' '}
            <span className="text-gradient-brand">ИТ-талантов</span>{' '}России
          </h1>

          <p
            className="text-lg text-text-secondary max-w-2xl mx-auto text-balance animate-fade-up"
            style={{ animationDelay: '0.2s' }}
          >
            Работодатель находит участников по протоколам ФСП и отправляет оффер.
            Имя и контакты открываются{' '}
            <strong className="text-text-primary font-semibold">только после согласия кандидата</strong>.
          </p>

          <div
            className="flex flex-col sm:flex-row gap-3 justify-center animate-fade-up"
            style={{ animationDelay: '0.3s' }}
          >
            <Link to="/register?role=participant" className="btn-primary text-base px-8 py-3">
              Я участник ФСП
            </Link>
            <Link to="/register?role=employer" className="btn-secondary text-base px-8 py-3">
              Я работодатель
            </Link>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-border py-8" aria-label="Статистика">
        <div className="max-w-7xl mx-auto px-6">
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {STATS.map(s => (
              <div key={s.label} className="text-center">
                <dt className="text-3xl font-bold text-gradient-brand tabular mb-1">{s.value}</dt>
                <dd className="text-xs text-text-muted uppercase tracking-widest">{s.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6" aria-labelledby="features-heading">
        <div className="max-w-7xl mx-auto">
          <h2 id="features-heading" className="text-3xl font-bold text-center mb-14 text-balance">
            Возможности платформы
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {FEATURES.map(({ icon: Icon, title, desc, accent, bg }) => (
              <div key={title} className={`card border ${bg} space-y-3`}>
                <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center`}>
                  <Icon size={20} className={accent} />
                </div>
                <h3 className="font-semibold text-text-primary">{title}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 text-center border-t border-border">
        <div className="max-w-lg mx-auto space-y-6">
          <h2 className="text-2xl font-bold">Готовы начать?</h2>
          <p className="text-text-secondary">Регистрация бесплатна. Анонимность гарантирована до оффера.</p>
          <Link to="/register?role=participant" className="btn-primary px-8 py-3 inline-flex">
            Зарегистрироваться
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8" role="contentinfo">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-text-muted">
            &copy; 2026 ФСП Талант · прототип · контакты только после согласия кандидата
          </p>
          <div className="flex items-center gap-4 text-xs text-text-muted">
            <Link to="/leaderboard" className="hover:text-text-primary transition-colors">Лидерборд</Link>
            <Link to="/login"       className="hover:text-text-primary transition-colors">Войти</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
