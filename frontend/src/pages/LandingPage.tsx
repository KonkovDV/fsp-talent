import { Link } from 'react-router-dom'
import { Code2, Shield, Trophy, Zap, Star } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-fsp-dark text-white">
      {/* Nav */}
      <nav className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <span className="text-xl font-bold text-fsp-violet">FSP Talent</span>
        <div className="flex items-center gap-4">
          <Link to="/leaderboard" className="text-gray-300 hover:text-white text-sm">Лидерборд</Link>
          <Link to="/login" className="text-gray-300 hover:text-white text-sm">Войти</Link>
          <Link to="/register" className="btn-primary text-sm">Зарегистрироваться</Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-24 text-center">
        <div className="inline-flex items-center gap-2 bg-fsp-violet/20 text-fsp-violet px-4 py-1.5 rounded-full text-sm font-medium mb-6">
          <Star size={14} /> LCT-2026
        </div>
        <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
          Маркетплейс<br />
          <span className="text-fsp-violet">ИТ-талантов</span> России
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10">
          Работодатель находит категорию участников по протоколам ФСП
          и отправляет оффер. Имя и контакты открываются только после согласия.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link to="/register?role=participant" className="btn-primary text-base px-8 py-3">
            Я участник ФСП
          </Link>
          <Link to="/register?role=employer" className="btn-secondary text-base px-8 py-3 border-white/30 text-white hover:bg-white hover:text-fsp-dark">
            Я работодатель
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="bg-white/5 py-20">
        <div className="max-w-7xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center mb-12">Возможности платформы</h2>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { icon: Trophy, title: 'Две оси', desc: 'Грейд по опыту. Уровень ФСП — процентиль, лестница ЕВСК и нижняя граница, а не место в протоколе' },
              { icon: Zap, title: 'Анонимный поиск', desc: 'Навыки, разряд-эквивалент и почему карточка в выдаче. Без имени до оффера' },
              { icon: Shield, title: 'Проверяемая подпись', desc: 'Платформа подписывает результат из ФСП. Подмена места ломает проверку' },
              { icon: Code2, title: '5 дисциплин', desc: 'Алгоритмика, продукт, безопасность, БАС, робототехника' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="bg-white/5 rounded-2xl p-6">
                <Icon className="text-fsp-violet mb-4" size={28} />
                <h3 className="font-semibold mb-2">{title}</h3>
                <p className="text-gray-400 text-sm">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-gray-500 text-sm">
          © 2026 ФСП Талант · прототип · контакты только после согласия кандидата
        </div>
      </footer>
    </div>
  )
}
