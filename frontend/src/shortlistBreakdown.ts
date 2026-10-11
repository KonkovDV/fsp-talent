import type { CandidateCardData } from './components/CandidateCard'

/**
 * Score breakdown for a shortlist row, taken from the current selection the page already loaded.
 * Empty when the candidate is not on the loaded page of the selection: no number is invented.
 */
export function shortlistBreakdown(candidateId: string, cards: CandidateCardData[] | undefined): string {
  const card = cards?.find(c => c.candidate_id === candidateId)
  const factors = card?.match?.factors.filter(f => f.value != null && f.contrib != null) ?? []
  return factors
    .map(f => `${f.label} ${(Math.round((f.contrib ?? 0) * 1000) / 10).toFixed(1).replace('.', ',')}`)
    .join(' · ')
}
