import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { TriangleAlert } from 'lucide-react'
import { publicDemo } from '../api/client'

/** Is this the hackathon demo stand? The server answers /public/demo from DEMO_MODE; on error we assume not. */
export function useDemoStand(): boolean {
  const { data } = useQuery({
    queryKey: ['public-demo'], retry: false, staleTime: 5 * 60_000,
    queryFn: () => publicDemo().then(r => Boolean(r.data.demo_mode)).catch(() => false),
  })
  return data === true
}

/**
 * 152-FZ art. 18 part 5: the demo stand runs on a server outside Russia, so people must not bring real
 * personal data there. Shown only with DEMO_MODE on; a production install never renders it.
 */
export default function DemoStandNotice({ className = '', withPolicyLink = false }: { className?: string; withPolicyLink?: boolean }) {
  const demo = useDemoStand()
  if (!demo) return null
  return (
    <div role="note" data-testid="demo-stand-notice"
      className={`notice border-warn/40 border-l-warn bg-warn-soft ${className}`}>
      <TriangleAlert size={18} className="mt-0.5 shrink-0 text-warn" aria-hidden />
      <div className="space-y-1">
        <p className="font-semibold">Это демо-стенд хакатона, и сервер стоит за пределами России</p>
        <p className="text-ink-2">
          Настоящие персональные данные сюда не вводите: ни своё имя, ни почту, ни телефон. Войдите демо-аккаунтом
          (жюри — jury1…jury10) или гостем и придумайте данные для пробы.
          {withPolicyLink && <> Подробнее — в <Link to="/privacy" className="underline">политике обработки данных</Link>.</>}
        </p>
      </div>
    </div>
  )
}
