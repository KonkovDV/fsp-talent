// Same rule as backend app/services/contact.py: e-mail, Telegram @handle or E.164 phone.
const EMAIL = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/
const TELEGRAM = /^@[A-Za-z0-9_]{5,32}$/
const PHONE = /^\+[1-9]\d{6,14}$/

export function contactOk(value: string): boolean {
  const parts = (value ?? '').split(/[;,]/).map(p => p.trim())
  if (parts.length === 0 || parts.length > 3 || parts.some(p => !p)) return false
  return parts.every(p => EMAIL.test(p) || TELEGRAM.test(p) || PHONE.test(p.replace(/[\s\-()]/g, '')))
}
