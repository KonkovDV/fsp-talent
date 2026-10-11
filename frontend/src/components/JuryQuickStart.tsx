import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiErrorCode, loginParticipant, publicJuryFree, startAssessment } from '../api/client'
import { useAuthStore } from '../store/authStore'

const JURY = /^jury([1-9]|10)@demo\.talent$/
// The published jury password: the same one the login page fills in for «Взять свободный аккаунт жюри».
const JURY_PASSWORD = 'demo12345'

/** Landing block for the jury: a five-minute express test in one click, demo logins and a three-step route. */
export default function JuryQuickStart() {
  const navigate = useNavigate()
  const setAuth = useAuthStore(s => s.setAuth)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const express = async () => {
    setBusy(true)
    setError('')
    try {
      const email = (await publicJuryFree()).data.email
      if (!JURY.test(email)) throw new Error('no free jury account')
      const res = await loginParticipant(email, JURY_PASSWORD)
      setAuth(res.data.access_token, 'participant')
      try {
        // The jury survey is empty on purpose, so the specialization is named here: backend, Python, junior.
        await startAssessment({ target_grade: 'junior', specialization: 'backend', code_language: 'python', mode: 'express' })
      } catch (e: unknown) {
        // An unfinished session of this account opens as is; the test page picks it up.
        if (apiErrorCode(e) !== 'conflict') throw e
      }
      navigate('/candidate/assessment')
    } catch {
      setError('Свободного аккаунта жюри сейчас нет или стенд не ответил.')
      setBusy(false)
    }
  }

  return (
    <div className="mt-8 max-w-xl rounded-xl border border-white/25 bg-white/[0.08] p-4 sm:p-5" data-testid="jury-quick-start">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-display text-sm font-bold">Войти как жюри</p>
        <Link to="/jury" className="btn-on-hero btn-sm">Маршрут для жюри</Link>
      </div>
      <button type="button" onClick={express} disabled={busy}
        className="btn mt-3 min-h-12 w-full bg-white px-6 text-base text-[#2A1DD6] hover:bg-white/90 disabled:opacity-70">
        {busy ? 'Открываем тест…' : 'Пройти экспресс-тест за 5 минут'}
      </button>
      <p className="mt-2 text-xs text-white/85">Без регистрации: свободный аккаунт jury1…jury10, 15 заданий, грейд не меняется.</p>
      {error && (
        <p className="mt-2 text-sm text-white" role="alert">
          {error} <Link to="/jury" className="font-medium underline">Открыть страницу жюри</Link>
        </p>
      )}
      <ol className="mt-4 list-decimal space-y-1 pl-5 text-sm text-white/90">
        <li>Кандидат: экспресс-тест — задания со своими числами у каждого, итог по темам.</li>
        <li>Работодатель <Link to="/login?role=employer" className="font-medium text-white underline">hr@sibcode.demo</Link>: потребность → подборка с объяснением → приглашение с вилкой.</li>
        <li>Методика: <Link to="/method" className="font-medium text-white underline">как устроен тест</Link> и <Link to="/badge" className="font-medium text-white underline">проверка удостоверения</Link>.</li>
      </ol>
      <p className="mt-3 text-xs text-white/80">
        Демо-входы, пароль demo12345: кандидат <Link to="/login" className="underline">fsp001@demo.talent</Link>, работодатель{' '}
        <Link to="/login?role=employer" className="underline">hr@sibcode.demo</Link>. Столы модерации и методиста открыты только
        сотрудникам: опубликованный логин их не видит.
      </p>
    </div>
  )
}
