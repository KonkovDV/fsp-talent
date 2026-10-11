// ТЗ 2.1: a stricter filter must not list more people. With role and grade the headline counts only the
// asked category; neighbours (one grade step, a neighbour role) are a separate, labelled number.
export function searchCount(total: number, inCategory: number | null | undefined): { main: number; related: number } {
  if (inCategory == null) return { main: total, related: 0 }
  const main = Math.max(0, Math.min(inCategory, total))
  return { main, related: total - main }
}
