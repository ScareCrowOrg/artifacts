/**
 * @file puyoStore.spec.ts
 * @description Tests for the puyo store state (game/reset) and the 1v1 read
 * helpers (opponentId / remoteGridOf).  ``usePuyoRealtime`` is thin glue over
 * ``useDistributedState`` (already covered elsewhere) and needs a Vue component
 * context, so it is not unit-tested here — matching party-game's gameStore.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { usePuyoStore, opponentId, remoteGridOf, type PuyoGameState } from '../store/puyoStore'

const grid = (fill = 1): number[] => Array.from({ length: 72 }, () => fill)

function runningGame(): PuyoGameState {
  return {
    status: 'running',
    seed: 42,
    round: 1,
    scores: { a: 10, b: 5 },
    readyFlags: { a: true, b: true },
    garbagePending: { a: 0, b: 6 },
    grids: { a: grid(2), b: grid(3) },
    gameOver: null,
  }
}

describe('usePuyoStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with a null game and resets', () => {
    const store = usePuyoStore()
    expect(store.game).toBeNull()
    store.game = runningGame()
    expect(store.game?.status).toBe('running')
    store.reset()
    expect(store.game).toBeNull()
  })

  it('holds the full snapshot shape', () => {
    const store = usePuyoStore()
    store.game = runningGame()
    const g = store.game
    expect(g?.seed).toBe(42)
    expect(g?.garbagePending.b).toBe(6)
    expect(g?.grids.b).toHaveLength(72)
  })
})

describe('opponentId', () => {
  it('returns the other 1v1 participant', () => {
    expect(opponentId(runningGame(), 'a')).toBe('b')
    expect(opponentId(runningGame(), 'b')).toBe('a')
  })

  it('returns null without a game or without myId', () => {
    expect(opponentId(null, 'a')).toBeNull()
    expect(opponentId(runningGame(), null)).toBeNull()
  })

  it('returns null when no opponent has a grid yet', () => {
    const g = runningGame()
    g.grids = {}
    expect(opponentId(g, 'a')).toBeNull()
  })
})

describe('remoteGridOf', () => {
  it('returns the opponent grid and null when absent', () => {
    const g = runningGame()
    expect(remoteGridOf(g, 'a')).toEqual(grid(3))
    expect(remoteGridOf(g, 'b')).toEqual(grid(2))
  })

  it('returns null when the opponent has not locked a piece', () => {
    const g = runningGame()
    g.grids = { a: grid(2) }
    expect(remoteGridOf(g, 'a')).toBeNull()
  })

  it('returns null without a game or myId', () => {
    expect(remoteGridOf(null, 'a')).toBeNull()
    expect(remoteGridOf(runningGame(), null)).toBeNull()
  })
})
