import { useEffect, useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiError, getEmployerMe, updateEmployerMe } from '../../api/client'
import { PageHeader } from '../../components/ui'

/** Company card the TZ asks the employer to keep: name, tax id, site, what the company does. */
export default function EmployerCompany() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['employerMe'], queryFn: () => getEmployerMe().then(r => r.data) })
  const [form, setForm] = useState({ company_name: '', inn: '', website: '', industry: '', description: '' })
  const [note, setNote] = useState('')
  const [error, setError] = useState('')

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

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [key]: e.target.value })

  return (
    <div>
      <PageHeader title="Компания" lead="Эти сведения видит кандидат в приглашении: название, чем вы занимаетесь и как с вами связаться." />
      <form className="card max-w-xl space-y-4" onSubmit={e => { e.preventDefault(); save.mutate() }}>
        <div><label className="field-label" htmlFor="co-name">Название</label>
          <input id="co-name" className="input" value={form.company_name} onChange={set('company_name')} required /></div>
        <div><label className="field-label" htmlFor="co-inn">ИНН</label>
          <input id="co-inn" className="input num" value={form.inn} onChange={set('inn')} inputMode="numeric" maxLength={12}
            placeholder="10 или 12 цифр" /></div>
        <div><label className="field-label" htmlFor="co-web">Сайт</label>
          <input id="co-web" className="input" value={form.website} onChange={set('website')} maxLength={200} /></div>
        <div><label className="field-label" htmlFor="co-ind">Отрасль</label>
          <input id="co-ind" className="input" value={form.industry} onChange={set('industry')} maxLength={200} /></div>
        <div><label className="field-label" htmlFor="co-desc">О компании</label>
          <textarea id="co-desc" className="input min-h-28" value={form.description} onChange={set('description')} maxLength={4000} /></div>
        {error && <p className="notice-error" role="alert">{error}</p>}
        {note && <p className="notice-ok" role="status">{note}</p>}
        <button className="btn-primary" type="submit" disabled={save.isPending}>Сохранить</button>
      </form>
    </div>
  )
}
