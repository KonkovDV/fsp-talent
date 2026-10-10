import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { apiError, getAiNote, type AiNotePoint } from '../api/client'

const PROVIDER_RU: Record<string, string> = { yandex: 'YandexGPT', gigachat: 'GigaChat', cloudru: 'Cloud.ru', mws: 'MWS GPT' }

function Points({ title, items, tone }: { title: string; items: AiNotePoint[]; tone: string }) {
  if (!items.length) return null
  return (
    <div>
      <p className="font-medium text-ink">{title}</p>
      <ul className="mt-1 space-y-1">
        {items.map(p => (
          <li key={p.text} className={tone}>
            {p.text}
            <span className="block text-xs text-ink-3">Основание: {p.facts.join('; ')}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Advisory model note. The score and the order of the list do not depend on it. */
export default function AiNote({ needId, candidateId }: { needId: string; candidateId: string }) {
  const note = useMutation({ mutationFn: () => getAiNote(needId, candidateId).then(r => r.data) })
  const data = note.data
  return (
    <div className="border-t border-line px-5 py-3 text-sm sm:px-6" data-testid="ai-note">
      {!data && (
        <button type="button" onClick={() => note.mutate()} disabled={note.isPending} className="btn-ghost -ml-3 gap-1 text-sm">
          <Sparkles size={16} aria-hidden />
          {note.isPending ? 'ИИ читает карточку…' : 'Мнение ИИ по карточке'}
        </button>
      )}
      {note.isError && <p role="alert" className="text-danger">{apiError(note.error)}</p>}
      {data && (
        <div className="space-y-3">
          <p className="text-xs text-ink-3">
            Сгенерировано ИИ ({PROVIDER_RU[data.provider] ?? data.provider}) только по фактам карточки, без имени и контактов.
            Не влияет на балл и порядок, решение принимает человек.
          </p>
          {data.summary && <p className="text-ink">{data.summary}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Points title="Сильные стороны" items={data.strengths} tone="text-ok" />
            <Points title="Что проверить" items={data.risks} tone="text-danger" />
          </div>
          <Points title="Вопросы для интервью" items={data.questions} tone="text-ink-2" />
          {!data.summary && !data.strengths.length && !data.risks.length && !data.questions.length && (
            <p className="text-ink-2">ИИ не сказал ничего, что подтверждается фактами карточки.</p>
          )}
          {data.dropped > 0 && <p className="text-xs text-ink-3">Отброшено пунктов без опоры на факты: {data.dropped}</p>}
        </div>
      )}
    </div>
  )
}
