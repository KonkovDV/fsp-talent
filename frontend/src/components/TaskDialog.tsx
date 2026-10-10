import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, X } from 'lucide-react'
import { apiError, createTask, getMyVacancies, labProblems, type TaskAnswerType } from '../api/client'
import { localDay } from '../lib/localDay'
import { ROLE_RU } from '../labels'
import Modal from './Modal'

const TEMPLATES: {
  id: string; label: string; title: string; statement: string; answer_type: TaskAnswerType
  reference_number?: string; options?: string[]; correct_index?: number; lab_id?: string
}[] = [
  {
    id: 'rows', label: 'Число: строки после фильтра', answer_type: 'number', reference_number: '6',
    title: 'Сколько строк останется',
    statement: 'В таблице events 20 строк. У 8 из них status = \'paid\', у 6 из этих восьми amount > 0.\n\nСколько строк вернёт запрос\nSELECT id FROM events WHERE status = \'paid\' AND amount > 0?',
  },
  {
    id: 'index', label: 'Выбор: какой индекс', answer_type: 'choice', correct_index: 1,
    options: ['(created_at)', '(customer_id, created_at DESC)', '(status)', '(id)'],
    title: 'Индекс для последних заказов клиента',
    statement: 'Запрос выбирает 20 последних заказов одного клиента:\nSELECT * FROM orders WHERE customer_id = $1 ORDER BY created_at DESC LIMIT 20.\n\nКакой индекс сильнее всего сузит поиск до начала сортировки?',
  },
  {
    id: 'idem', label: 'Открытый ответ: повтор оплаты', answer_type: 'open',
    title: 'Повторный запрос оплаты',
    statement: 'Клиент дважды отправил одну и ту же оплату. Опишите, как API отличит повтор от нового платежа: что сохранить, что вернуть на повтор и что не списать второй раз. Достаточно подхода, код не обязателен.',
  },
  {
    id: 'lab', label: 'Код: лаборатория', answer_type: 'code', lab_id: 'sum_positive',
    title: '', statement: '',
  },
]

const TYPES: { value: TaskAnswerType; label: string; hint: string }[] = [
  { value: 'number', label: 'Число', hint: 'Проверит система по эталону' },
  { value: 'choice', label: 'Выбор варианта', hint: 'Проверит система по эталону' },
  { value: 'open', label: 'Открытый ответ', hint: 'Скрипт или решение: проверяете вы' },
  { value: 'code', label: 'Код', hint: 'Скрытые проверки. Грейд не меняется' },
]

/**
 * A task written by the employer. Addressed to one candidate when opened from a card (candidateId),
 * otherwise public for every candidate of the chosen specialization.
 */
export default function TaskDialog({ candidateId, candidateLabel, defaultSpec = 'backend', onClose, onCreated }: {
  candidateId?: string; candidateLabel?: string; defaultSpec?: string; onClose: () => void; onCreated?: () => void
}) {
  const qc = useQueryClient()
  const { data: vacancies = [] } = useQuery<{ id: string; title: string; is_open: boolean }[]>({
    queryKey: ['myVacancies'], queryFn: () => getMyVacancies().then(r => r.data),
  })
  const { data: problems = [] } = useQuery({ queryKey: ['labProblems'], queryFn: () => labProblems().then(r => r.data) })
  const [form, setForm] = useState({
    title: '', statement: '', answer_type: 'number' as TaskAnswerType, reference_number: '',
    lab_id: 'sum_positive', options: ['', ''], correct_index: 0, specialization: defaultSpec, vacancy_id: '', deadline: '',
  })
  const [error, setError] = useState('')
  const send = useMutation({
    mutationFn: () => createTask({
      title: form.title.trim(), statement: form.statement.trim(), answer_type: form.answer_type,
      reference_number: form.answer_type === 'number' ? form.reference_number.trim()
        : form.answer_type === 'code' ? form.lab_id : null,
      options: form.answer_type === 'choice' ? form.options.map(o => o.trim()) : [],
      correct_index: form.answer_type === 'choice' ? form.correct_index : null,
      visibility: candidateId ? 'addressed' : 'public', candidate_id: candidateId ?? null,
      specialization: candidateId ? null : form.specialization,
      vacancy_id: form.vacancy_id || null,
      deadline: form.deadline ? new Date(`${form.deadline}T23:59:00`).toISOString() : null,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['employerTasks'] }); onCreated?.(); onClose() },
    onError: e => setError(apiError(e, 'Задание не создано')),
  })
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const catalog = problems.find(p => p.id === form.lab_id)
    if (form.answer_type === 'code' && catalog && form.statement.trim().length < 10) {
      form.statement = catalog.statement
    }
    if (form.answer_type === 'code' && catalog && form.title.trim().length < 3) {
      form.title = catalog.title
    }
    if (form.title.trim().length < 3) return setError('Назовите задание')
    if (form.statement.trim().length < 10) return setError('Опишите условие')
    if (form.answer_type === 'number' && !/^\s*-?\d+\s*$/.test(form.reference_number)) return setError('Эталон — целое число')
    if (form.answer_type === 'choice' && form.options.some(o => !o.trim())) return setError('Заполните все варианты')
    setError('')
    send.mutate()
  }
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value })
  const setOption = (i: number, v: string) => setForm({ ...form, options: form.options.map((o, j) => (j === i ? v : o)) })
  const dropOption = (i: number) => setForm({
    ...form, options: form.options.filter((_, j) => j !== i),
    correct_index: form.correct_index === i ? 0 : form.correct_index > i ? form.correct_index - 1 : form.correct_index,
  })
  const today = localDay()
  const applyTemplate = (id: string) => {
    const tpl = TEMPLATES.find(item => item.id === id)
    if (!tpl) return
    const catalog = problems.find(p => p.id === (tpl.lab_id ?? form.lab_id))
    setForm({
      ...form,
      answer_type: tpl.answer_type,
      title: tpl.title || catalog?.title || form.title,
      statement: tpl.statement || catalog?.statement || form.statement,
      reference_number: tpl.reference_number ?? form.reference_number,
      options: tpl.options ?? form.options,
      correct_index: tpl.correct_index ?? form.correct_index,
      lab_id: tpl.lab_id ?? form.lab_id,
    })
  }

  return (
    <Modal titleId="task-title" onClose={onClose} sheet>
      <form onSubmit={submit} className="w-full rounded-t-2xl border border-line bg-panel p-6 shadow-pop sm:rounded-2xl sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="task-title" className="font-display text-lg font-bold text-ink">{candidateId ? 'Задание кандидату' : 'Новое задание'}</h2>
            <p className="mt-1 text-sm text-ink-2">
              {candidateId
                ? `Увидит только этот кандидат${candidateLabel ? ` (${candidateLabel})` : ''}. Его имя и контакты задание не открывает.`
                : 'Увидят все кандидаты выбранной специализации. Эталон ответа кандидат не видит, пока не ответит.'}
            </p>
          </div>
          <button type="button" onClick={onClose} className="btn-icon" aria-label="Закрыть"><X size={18} /></button>
        </div>
        <div className="mt-5 max-h-[62dvh] space-y-4 overflow-y-auto pr-1">
          <div><label className="field-label" htmlFor="t-template">Шаблон, если нужен</label>
            <select id="t-template" className="select" defaultValue="" onChange={e => applyTemplate(e.target.value)}>
              <option value="">Свой текст</option>
              {TEMPLATES.map(tpl => <option key={tpl.id} value={tpl.id}>{tpl.label}</option>)}
            </select>
            <p className="field-hint">Шаблон только заполняет поля. Число и выбор проверяет система, открытый ответ смотрите вы. Грейд не меняется.</p>
          </div>
          <div><label className="field-label" htmlFor="t-title">Название</label>
            <input id="t-title" value={form.title} onChange={set('title')} className="input" maxLength={200}
              placeholder="Сколько строк вернёт запрос" autoFocus /></div>
          <div><label className="field-label" htmlFor="t-text">Условие</label>
            <textarea id="t-text" value={form.statement} onChange={set('statement')} rows={5} maxLength={4000}
              className="input resize-y font-mono text-[13px]" placeholder="Что дано и что нужно найти или предложить" /></div>
          <fieldset>
            <legend className="field-label">Ответ</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {TYPES.map(t => (
                <label key={t.value} className={`flex cursor-pointer flex-col rounded-lg border p-3 text-sm ${form.answer_type === t.value ? 'border-accent bg-accent-soft' : 'border-line hover:border-line-strong'}`}>
                  <span className="flex items-center gap-2 font-medium text-ink">
                    <input type="radio" name="t-type" value={t.value} checked={form.answer_type === t.value}
                      onChange={() => setForm({ ...form, answer_type: t.value })} />{t.label}
                  </span>
                  <span className="mt-1 text-xs text-ink-2">{t.hint}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {form.answer_type === 'number' && (
            <div><label className="field-label" htmlFor="t-ref">Эталон: целое число</label>
              <input id="t-ref" value={form.reference_number} onChange={set('reference_number')} inputMode="numeric"
                className="input num w-40" placeholder="500" /></div>
          )}
          {form.answer_type === 'code' && (
            <div>
              <label className="field-label" htmlFor="t-lab">Задание лаборатории</label>
              <select id="t-lab" value={form.lab_id} onChange={set('lab_id')} className="select">
                {problems.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
              <p className="field-hint">{problems.find(p => p.id === form.lab_id)?.statement}</p>
              <p className="field-hint">Кандидат пишет на Python или JavaScript. Скрытые примеры ему не показываются. Грейд и подбор не меняются.</p>
            </div>
          )}
          {form.answer_type === 'choice' && (
            <fieldset className="space-y-2">
              <legend className="field-label">Варианты, отметьте правильный</legend>
              {form.options.map((o, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input type="radio" name="t-right" checked={form.correct_index === i} aria-label={`Вариант ${i + 1} правильный`}
                    onChange={() => setForm({ ...form, correct_index: i })} />
                  <input value={o} onChange={e => setOption(i, e.target.value)} className="input" aria-label={`Вариант ${i + 1}`} maxLength={300} />
                  {form.options.length > 2 && (
                    <button type="button" onClick={() => dropOption(i)} className="btn-ghost h-9 w-9 shrink-0 p-0" aria-label={`Убрать вариант ${i + 1}`}><Trash2 size={15} /></button>
                  )}
                </div>
              ))}
              {form.options.length < 8 && (
                <button type="button" onClick={() => setForm({ ...form, options: [...form.options, ''] })} className="btn-ghost btn-sm -ml-3">
                  <Plus size={14} aria-hidden /> Добавить вариант
                </button>
              )}
            </fieldset>
          )}
          <div className="grid gap-3 sm:grid-cols-3">
            {!candidateId && (
              <div><label className="field-label" htmlFor="t-spec">Специализация</label>
                <select id="t-spec" value={form.specialization} onChange={set('specialization')} className="select">
                  {Object.entries(ROLE_RU).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select></div>
            )}
            <div><label className="field-label" htmlFor="t-vac">Вакансия, если нужно</label>
              <select id="t-vac" value={form.vacancy_id} onChange={set('vacancy_id')} className="select">
                <option value="">без вакансии</option>
                {vacancies.filter(v => v.is_open).map(v => <option key={v.id} value={v.id}>{v.title}</option>)}
              </select></div>
            <div><label className="field-label" htmlFor="t-deadline">Срок, если нужен</label>
              <input id="t-deadline" type="date" min={today} value={form.deadline} onChange={set('deadline')} className="input" /></div>
          </div>
        </div>
        {error && <p className="notice-error mt-4" role="alert">{error}</p>}
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-secondary">Отмена</button>
          <button type="submit" disabled={send.isPending} className="btn-primary">{send.isPending ? 'Отправляем…' : candidateId ? 'Отправить задание' : 'Опубликовать'}</button>
        </div>
      </form>
    </Modal>
  )
}
