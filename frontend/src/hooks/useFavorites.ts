import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listFavorites, setFavorite, setFavoriteInterest } from '../api/client'
import type { CandidateCardData } from '../components/CandidateCard'

export interface FavoritesData {
  items: (CandidateCardData & { saved_at: string; interest?: 'saved' | 'priority'; returned_interest?: boolean })[]
  ids: string[]
  hidden: number
  max: number
}

/** The company's favorites, shared by search, need matches and the favorites page. */
export function useFavorites() {
  const qc = useQueryClient()
  const query = useQuery<FavoritesData>({
    queryKey: ['favorites'],
    queryFn: () => listFavorites().then(r => r.data),
  })
  const toggle = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => setFavorite(id, on),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['favorites'] }),
  })
  const interest = useMutation({
    mutationFn: ({ id, value }: { id: string; value: 'saved' | 'priority' }) => setFavoriteInterest(id, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['favorites'] }),
  })
  const ids = new Set(query.data?.ids ?? [])
  return {
    query,
    has: (id: string) => ids.has(id),
    toggle: (id: string, on: boolean) => toggle.mutate({ id, on }),
    setInterest: (id: string, value: 'saved' | 'priority') => interest.mutate({ id, value }),
    error: toggle.error,
  }
}
