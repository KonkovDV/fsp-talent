import { afterEach, describe, expect, it } from 'vitest'
import {
  diffSelection,
  formatSelectionSummary,
  loadSnapshot,
  ranksFromIds,
  saveSnapshot,
  selectionStorageKey,
} from './selectionDiff'

afterEach(() => {
  localStorage.clear()
})

describe('diffSelection', () => {
  it('пустая история — без меток и счётчиков', () => {
    const next = ranksFromIds(['a', 'b', 'c'])
    expect(diffSelection(null, next)).toEqual({ added: 0, removed: 0, moved: 0, markers: {} })
    expect(diffSelection([], next)).toEqual({ added: 0, removed: 0, moved: 0, markers: {} })
  })

  it('новые, выбывшие и сдвиги', () => {
    const prev = ranksFromIds(['a', 'b', 'c', 'd'])
    const next = ranksFromIds(['c', 'a', 'e'])
    const diff = diffSelection(prev, next)
    expect(diff.added).toBe(1)
    expect(diff.removed).toBe(2)
    expect(diff.moved).toBe(2)
    expect(diff.markers).toEqual({ e: 'new', c: 'up', a: 'down' })
    expect(formatSelectionSummary(diff)).toBe('+1 новый · −2 выбыли · 2 сдвинулись')
  })

  it('без изменений — summary null', () => {
    const ranks = ranksFromIds(['a', 'b'])
    const diff = diffSelection(ranks, ranks)
    expect(diff).toEqual({ added: 0, removed: 0, moved: 0, markers: {} })
    expect(formatSelectionSummary(diff)).toBeNull()
  })
})

describe('localStorage snapshot', () => {
  it('сохраняет и читает по need_id', () => {
    const ranks = ranksFromIds(['x', 'y'])
    saveSnapshot('need-1', ranks)
    expect(localStorage.getItem(selectionStorageKey('need-1'))).toBeTruthy()
    expect(loadSnapshot('need-1')).toEqual(ranks)
    expect(loadSnapshot('other')).toBeNull()
  })
})
