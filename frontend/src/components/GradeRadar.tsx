import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip
} from 'recharts'

interface Props {
  scores: { discipline: string; score: number; confidence: number }[]
}

const DISC_LABELS: Record<string, string> = {
  algorithmic: 'Алгоритмика',
  product: 'Продукт',
  security: 'Безопасность',
  bas: 'BAS',
  robotics: 'Робототехника',
}

export default function GradeRadar({ scores }: Props) {
  const data = scores.map(s => ({
    subject: DISC_LABELS[s.discipline] ?? s.discipline,
    value: Math.round(s.score * 100),
    fullMark: 100,
  }))
  if (!data.length) return <p className="text-gray-400 text-sm">Нет оценок по дисциплинам</p>
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data}>
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis dataKey="subject" tick={{ fill: '#6b7280', fontSize: 12 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
        <Radar name="Уровень" dataKey="value" stroke="#402FFF" fill="#402FFF" fillOpacity={0.2} />
        <Tooltip formatter={(v: number) => [`${v}%`, 'Уровень']} />
      </RadarChart>
    </ResponsiveContainer>
  )
}
