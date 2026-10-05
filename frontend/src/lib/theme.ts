import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'

function current(): Theme {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'
}

/** Theme toggle shared by every shell. The choice is remembered; without one the system setting wins. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(current)
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])
  const toggle = () => setTheme(t => {
    const next = t === 'dark' ? 'light' : 'dark'
    try { localStorage.setItem('fsp-theme', next) } catch { /* private mode */ }
    return next
  })
  return [theme, toggle]
}
