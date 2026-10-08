import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => {
        const status = (error as { response?: { status?: number } })?.response?.status
        return count < 1 && !(status !== undefined && status >= 400 && status < 500)
      },
    },
  },
})

/** React Query is not needed for the first screen, so it loads with the next route. */
export default function QueryShell() {
  const [wait, setWait] = useState<number | null>(null)
  useEffect(() => {
    const onLimit = (event: Event) => {
      const seconds = (event as CustomEvent<number>).detail
      setWait(seconds)
    }
    window.addEventListener('fsp-rate-limit', onLimit)
    return () => window.removeEventListener('fsp-rate-limit', onLimit)
  }, [])
  return (
    <QueryClientProvider client={queryClient}>
      {wait !== null && (
        <p className="notice-info mx-auto mt-4 max-w-page" role="status">Подождите {wait} с</p>
      )}
      <Outlet />
    </QueryClientProvider>
  )
}
