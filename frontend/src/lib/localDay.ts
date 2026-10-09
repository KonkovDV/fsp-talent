/** Calendar day in the viewer's zone.

A UTC date is still yesterday in the morning east of Greenwich, so a date input
must not use `toISOString().slice(0, 10)` as "today".
*/
export function localDay(now = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
