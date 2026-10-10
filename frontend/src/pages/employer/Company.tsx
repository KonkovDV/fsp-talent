import { useEffect, useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, atsSandbox, getEmployerMe, getReputation, saveHiringPractice, updateEmployerMe } from '../../api/client'
import AccountSecurity from '../../components/AccountSecurity'
import { PageHeader } from '../../components/ui'

/** Company card the TZ asks the employer to keep: name, tax id, site, what the company does. */
export default function EmployerCompany() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['employerMe'], queryFn: () => getEmployerMe().then(r => r.data) })
  const facts = useQuery({ queryKey: ['reputation'], queryFn: () => getReputation().then(r => r.data) })
  const [form, setForm] = useState({ company_name: '', inn: '', website: '', industry: '', description: '' })
  const [note, setNote] = useState('')
  const [practice, setPractice] = useState({ feedback: false, platform_interview: false, task_review: false, salary_written: false })
  const [practiceNote, setPracticeNote] = useState('')
  const [error, setError] = useState('')
  const [slip, setSlip] = useState<{ signature: string; valid: boolean; delivered: boolean; event: { type: string } } | null>(null)
  const [slipError, setSlipError] = useState('')

  useEffect(() => {
    if (!data) return
    setForm({
      company_name: data.company_name ?? '',
      inn: data.inn ?? '',
      website: data.website ?? '',
      industry: data.industry ?? '',
      description: data.description ?? '',
    })
  }, [data])

  const save = useMutation({
    mutationFn: () => updateEmployerMe({
      company_name: form.company_name,
      inn: form.inn || null,
      website: form.website || null,
      industry: form.industry || null,
      description: form.description || null,
    }),
    onSuccess: () => { setError(''); setNote('Сохранено'); qc.invalidateQueries({ queryKey: ['employerMe'] }) },
    onError: (e: unknown) => { setNote(''); setError(apiError(e, 'Не сохранилось')) },
  })

  const showSlip = useMutation({
    mutationFn: () => atsSandbox().then(r => r.data),
    onSuccess: (data) => { setSlipError(''); setSlip(data) },
    onError: (e: unknown) => { setSlip(null); setSlipError(apiError(e, 'Квитанция не собрана')) },
  })

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value })

  return (
    <div>
      <PageHeader title="Компания" lead="Эти сведения видит кандидат в приглашении: название, чем вы занимаетесь и как с вами связаться." />
      {facts.data && (
        <p className="mb-4 text-sm text-ink-2">
          На платформе {facts.data.tenure_days ?? '—'} дн. Ответ после согласия: {facts.data.reply.shown ? `не ниже ${Math.round(facts.data.reply.lower * 100)}% из ${facts.data.reply.n}` : 'мало данных'}.
          Собеседование: {facts.data.interview.shown ? `не ниже ${Math.round(facts.data.interview.lower * 100)}% из ${facts.data.interview.n}` : 'мало данных'}.
          Жалобы: {facts.data.complaints.shown ? `${facts.data.complaints.count} из ${facts.data.complaints.n}` : 'мало данных'}.
          Общей оценки нет.
        </p>
      )}
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_1fr]">
      <form className="card space-y-4" onSubmit={e => { e.preventDefault(); save.mutate() }}>
        <div><label className="field-label" htmlFor="co-name">Название</label>
          <input id="co-name" className="input" value={form.company_name} onChange={set('company_name')} required /></div>
        <div><label className="field-label" htmlFor="co-inn">ИНН</label>
          <input id="co-inn" className="input num" value={form.inn} onChange={set('inn')} inputMode="numeric" maxLength={12}
            placeholder="10 или 12 цифр" /></div>
        <div><label className="field-label" htmlFor="co-web">Сайт</label>
          <input id="co-web" className="input" value={form.website} onChange={set('website')} maxLength={200} /></div>
        <div><label className="field-label" htmlFor="co-ind">Сфера</label>
          <input id="co-ind" className="input" value={form.industry} onChange={set('industry')} maxLength={200} /></div>
        <div><label className="field-label" htmlFor="co-desc">О компании</label>
          <textarea id="co-desc" className="input min-h-28" value={form.description} onChange={set('description')} maxLength={4000} /></div>
        {error && <p className="notice-error" role="alert">{error}</p>}
        {note && <p className="notice-ok" role="status">{note}</p>}
        <button className="btn-primary" type="submit" disabled={save.isPending}>Сохранить</button>
      </form>
      <form className="card space-y-3" onSubmit={e => {
        e.preventDefault()
        saveHiringPractice(practice).then(() => setPracticeNote('Ответы сохранены.')).catch((err: unknown) => setPracticeNote(apiError(err, 'Не сохранилось')))
      }}>
        <h2 className="section-title">Как вы нанимаете</h2>
        <p className="text-sm text-ink-2">Ответы сохраняются. Уровень по ним компания не видит.</p>
        {([
          ['feedback', 'Письменный ответ кандидату, если не зовём дальше'],
          ['platform_interview', 'Собеседование назначаем на платформе'],
          ['task_review', 'Задание проверяем и пишем комментарий'],
          ['salary_written', 'Вилка есть в приглашении до ответа кандидата'],
        ] as const).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={practice[key]} onChange={e => setPractice(prev => ({ ...prev, [key]: e.target.checked }))} />
            {label}
          </label>
        ))}
        <button type="submit" className="btn-secondary btn-sm">Сохранить ответы</button>
        {practiceNote && <p className="text-sm text-ink-2" role="status">{practiceNote}</p>}
      </form>
      <aside className="lg:sticky lg:top-36" aria-label="Как кандидат увидит приглашение">
        <p className="field-label">Так кандидат увидит приглашение</p>
        <div className="card p-0">
          <div className="flex items-start gap-3 border-b border-line p-5">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-accent-soft font-display text-lg font-bold text-accent" aria-hidden>
              {(form.company_name || '?').slice(0, 1)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-ink">Backend-разработчик</p>
              <p className="text-sm text-ink-2">{form.company_name || 'Название компании'}{form.industry ? `, ${form.industry}` : ''}</p>
              {data?.trust_label && <p className="text-xs text-ink-3">Уровень доверия {data.trust_level}: {data.trust_label}. Уровень считает платформа, в форме его нет.</p>}
            </div>
            <p className="text-right font-display text-sm font-bold text-ink num">180 000 ₽<span className="block text-xs font-normal text-ink-3">до 240 000 ₽</span></p>
          </div>
          <div className="space-y-3 p-5 text-sm">
            <p className={form.description ? 'text-ink-2' : 'text-ink-3'}>{form.description || 'Здесь будет текст «О компании». Две-три фразы о продукте и команде помогают кандидату принять приглашение.'}</p>
            <p className="flex flex-wrap gap-x-4 gap-y-1 text-ink-3">
              {form.website && <span>{form.website}</span>}
              <span className={data?.inn_checked && form.inn === data.inn ? 'text-ok' : ''}>
                {data?.inn_checked && form.inn === data.inn
                  ? 'ИНН указан и проверен по контрольной сумме'
                  : form.inn
                    ? 'Контрольная сумма ИНН проверяется при сохранении'
                    : 'ИНН не указан: кандидату спокойнее отвечать компании с проверенным ИНН'}
              </span>
            </p>
            <div className="flex gap-2 pt-1">
              <span className="btn-primary btn-sm pointer-events-none">Принять</span>
              <span className="btn-secondary btn-sm pointer-events-none">Отклонить</span>
            </div>
          </div>
        </div>
        <p className="field-hint mt-2">Роль и зарплата в примере условные: в настоящем приглашении — те, что вы укажете.</p>
      </aside>
      </div>
      <section className="card mt-6 max-w-xl space-y-3" aria-label="Квитанция ATS">
        <h2 className="font-medium text-ink">Квитанция ATS</h2>
        <p className="text-sm text-ink-2">Пример события «приглашение принято» подписывается на стенде. Контактов в нём нет, адрес наружу не вызывается.</p>
        <button type="button" className="btn-secondary" disabled={showSlip.isPending} onClick={() => showSlip.mutate()}>Показать квитанцию</button>
        {slipError && <p className="notice-error" role="alert">{slipError}</p>}
        {slip && (
          <p className="text-sm text-ink" role="status">
            {slip.event.type}. Подпись {slip.valid ? 'сходится' : 'не сходится'}. {slip.delivered ? 'Отправлено.' : 'Никуда не отправлено.'}
            <span className="mt-1 block break-all font-mono text-xs text-ink-3">{slip.signature}</span>
          </p>
        )}
      </section>
      <div className="mt-6 max-w-xl">
        <AccountSecurity />
      </div>
    </div>
  )
}
