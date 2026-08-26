/**
 * @file PuyoRNG.ts
 * @description Deterministic PRNG (mulberry32) for the Puyo Party cell.
 *
 * Lockstep model: the backend generates a single ``seed`` and both clients
 * derive the SAME piece sequence from it — no piece choices travel over the
 * network.  ``PuyoRNG`` is a thin wrapper over ``mulberry32`` exposing
 * puyo-friendly draws (colors 1..4 and piece pairs).
 */

/** Number of distinct puyo colors (classic Puyo Puyo uses 4). */
export const PUYO_COLOR_COUNT = 4

export interface PuyoPair {
  /** Color of the leading puyo (1..PUYO_COLOR_COUNT). */
  a: number
  /** Color of the trailing puyo (1..PUYO_COLOR_COUNT). */
  b: number
}

/**
 * mulberry32 — fast, deterministic 32-bit PRNG.
 *
 * @param seed Any 32-bit integer.  The same seed always yields the same
 *   sequence (lockstep guarantee across clients).
 * @returns A function returning floats in [0, 1).
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export class PuyoRNG {
  private readonly nextFloat: () => number

  constructor(seed: number) {
    this.nextFloat = mulberry32(seed)
  }

  /** Next float in [0, 1). */
  next(): number {
    return this.nextFloat()
  }

  /** Next puyo color id in 1..PUYO_COLOR_COUNT (inclusive). */
  nextColor(): number {
    return 1 + Math.floor(this.next() * PUYO_COLOR_COUNT)
  }

  /** Next piece pair — the atomic unit of the deterministic queue. */
  pair(): PuyoPair {
    return { a: this.nextColor(), b: this.nextColor() }
  }
}
