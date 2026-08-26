/**
 * @file PuyoRNG.spec.ts
 * @description Determinism tests for the lockstep PRNG.
 *
 * Lockstep guarantee: two clients built from the SAME seed must derive the
 * SAME piece sequence — this is what makes the game playable without sending
 * piece choices over the network.
 */

import { describe, it, expect } from 'vitest'
import { PuyoRNG, mulberry32, PUYO_COLOR_COUNT } from '../engine/PuyoRNG'

describe('mulberry32', () => {
  it('returns floats in [0, 1)', () => {
    const next = mulberry32(12345)
    for (let i = 0; i < 1000; i++) {
      const v = next()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThan(1)
    }
  })

  it('is deterministic for the same seed', () => {
    const a = mulberry32(42)
    const b = mulberry32(42)
    for (let i = 0; i < 100; i++) {
      expect(a()).toBe(b())
    }
  })

  it('produces different sequences for different seeds', () => {
    const a = mulberry32(1)
    const b = mulberry32(2)
    const seqA = Array.from({ length: 10 }, () => a())
    const seqB = Array.from({ length: 10 }, () => b())
    expect(seqA).not.toEqual(seqB)
  })
})

describe('PuyoRNG', () => {
  it('yields the same full sequence for the same seed', () => {
    const a = new PuyoRNG(777)
    const b = new PuyoRNG(777)
    for (let i = 0; i < 50; i++) {
      expect(a.next()).toBe(b.next())
      expect(a.nextColor()).toBe(b.nextColor())
      expect(a.pair()).toEqual(b.pair())
    }
  })

  it('yields colors only in 1..PUYO_COLOR_COUNT', () => {
    const rng = new PuyoRNG(2026)
    for (let i = 0; i < 500; i++) {
      const color = rng.nextColor()
      expect(color).toBeGreaterThanOrEqual(1)
      expect(color).toBeLessThanOrEqual(PUYO_COLOR_COUNT)
    }
  })

  it('pairs have both colors in range', () => {
    const rng = new PuyoRNG(1)
    for (let i = 0; i < 100; i++) {
      const pair = rng.pair()
      expect(pair.a).toBeGreaterThanOrEqual(1)
      expect(pair.a).toBeLessThanOrEqual(PUYO_COLOR_COUNT)
      expect(pair.b).toBeGreaterThanOrEqual(1)
      expect(pair.b).toBeLessThanOrEqual(PUYO_COLOR_COUNT)
    }
  })

  it('two clients with the same seed agree on the piece queue', () => {
    const clientA = new PuyoRNG(31337)
    const clientB = new PuyoRNG(31337)
    const queueA = Array.from({ length: 30 }, () => clientA.pair())
    const queueB = Array.from({ length: 30 }, () => clientB.pair())
    expect(queueA).toEqual(queueB)
  })
})
