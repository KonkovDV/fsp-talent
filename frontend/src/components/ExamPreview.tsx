export interface ExamTopic { topic: string; label: string; share: number }
export interface ExamSample { topic: string; topic_label?: string; family: string; stem: string; code?: string | null; language?: string | null }
export interface Exam { why: string; topics: ExamTopic[]; samples: ExamSample[]; quotes?: { skill: string; evidence: string }[] }

// One hue, stepped by order: the bar shows parts of a whole, the labels carry the names.
const STEPS = ['bg-accent', 'bg-accent/80', 'bg-accent/60', 'bg-accent/45', 'bg-accent/35', 'bg-accent/25']

/** What test a need or vacancy forms: topic shares, the quotes they came from, sample items without keys. */
export default function ExamPreview({ exam }: { exam: Exam }) {
  return (
    <div className="space-y-5">
      <p className="text-sm text-ink">{exam.why}</p>
      <div>
        <div className="flex h-3 overflow-hidden rounded-full bg-sunken" role="img"
          aria-label={exam.topics.map(t => `${t.label} ${Math.round(t.share * 100)} %`).join(', ')}>
          {exam.topics.map((t, i) => <span key={t.topic} className={`${STEPS[i % STEPS.length]} border-r-2 border-panel last:border-r-0`} style={{ width: `${t.share * 100}%` }} />)}
        </div>
        <ul className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
          {exam.topics.map((t, i) => (
            <li key={t.topic} className="flex items-center gap-2 text-ink-2">
              <span className={`h-2.5 w-2.5 rounded-sm ${STEPS[i % STEPS.length]}`} aria-hidden />
              {t.label} <span className="num font-semibold text-ink">{Math.round(t.share * 100)} %</span>
            </li>
          ))}
        </ul>
      </div>
      {exam.quotes && exam.quotes.length > 0 && (
        <div>
          <p className="field-label">Откуда темы</p>
          <ul className="space-y-1 text-sm text-ink-2">
            {exam.quotes.map(q => <li key={q.skill}><span className="font-medium text-ink">{q.skill}</span> — «{q.evidence}»</li>)}
          </ul>
        </div>
      )}
      {exam.samples.length > 0 && (
        <div>
          <p className="field-label">Примеры заданий, ответ не показывается</p>
          <ol className="space-y-4">
            {exam.samples.map(s => (
              <li key={s.stem} className="space-y-2">
                <p className={`whitespace-pre-wrap text-sm text-ink ${s.stem.includes(' | ') ? 'font-mono text-xs' : ''}`}><span className="font-sans text-ink-3">{s.topic_label ?? s.family}.</span> {s.stem}</p>
                {s.code && <pre className="code-block"><code>{s.code}</code></pre>}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
