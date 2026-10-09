/** One-time secrets from a letter belong in the fragment, then in this tab, never in the query string. */

const memory = new Map<string, string>()
const started = new Map<string, Promise<unknown>>()

function path(): string {
  return window.location.pathname
}

function key(pathname: string): string {
  return `fsp.letter:${pathname}`
}

function readStored(pathname: string): string {
  const kept = memory.get(pathname)
  if (kept) return kept
  try { return sessionStorage.getItem(key(pathname)) ?? '' } catch { return '' }
}

function remember(pathname: string, token: string): void {
  memory.set(pathname, token)
  try { sessionStorage.setItem(key(pathname), token) } catch { /* private mode */ }
}

function freshToken(): string {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const query = new URLSearchParams(window.location.search)
  return hash.get('token') || query.get('token') || ''
}

export function letterToken(): string {
  const here = path()
  const fresh = freshToken()
  if (fresh) {
    remember(here, fresh)
    return fresh
  }
  // A query without the secret is another entry, such as the form after registration.
  if (window.location.search) {
    memory.delete(here)
    try { sessionStorage.removeItem(key(here)) } catch { /* private mode */ }
    return ''
  }
  return readStored(here)
}

export function dropLetterToken(): void {
  const here = path()
  const fresh = freshToken()
  if (fresh) remember(here, fresh)
  const next = new URLSearchParams(window.location.search)
  if (!next.has('token') && !window.location.hash) return
  next.delete('token')
  const q = next.toString()
  window.history.replaceState(null, '', here + (q ? `?${q}` : ''))
}

export function forgetLetterToken(): void {
  const here = path()
  memory.delete(here)
  try { sessionStorage.removeItem(key(here)) } catch { /* private mode */ }
}

/** The same letter token starts one request, even if the page mounts twice. */
export function onceLetter<T>(token: string, run: () => Promise<T>): Promise<T> | null {
  if (!token) return null
  const id = `${path()}:${token}`
  const found = started.get(id) as Promise<T> | undefined
  if (found) return found
  const job = run()
  started.set(id, job)
  return job
}
