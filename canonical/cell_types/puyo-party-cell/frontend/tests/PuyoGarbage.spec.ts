/**
 * @file PuyoGarbage.spec.ts
 * @description Garbage mechanics tests — stone count, attack formula and
 * in-board distribution.
 */

import { describe, it, expect } from 'vitest'
import { calculateGarbage } from '../engine/PuyoGarbage'
// Board-side garbage mechanics live in PuyoBoard (single source of truth).
import { applyGarbageToGrid, garbageStoneCount, createEmptyBoard, GARBAGE_COLOR } from '../engine/PuyoBoard'

describe('garbageStoneCount', () => {
  it('converts units to 2 stones each', () => {
    expect(garbageStoneCount(1)).toBe(2)
    expect(garbageStoneCount(6)).toBe(12)
    expect(garbageStoneCount(0)).toBe(0)
  })

  it('sanitizes negatives and fractions', () => {
    expect(garbageStoneCount(-3)).toBe(0)
    expect(garbageStoneCount(2.9)).toBe(4)
  })
})

describe('calculateGarbage', () => {
  it('returns 0 for a single (non-chain) clear', () => {
    expect(calculateGarbage(0, 4)).toBe(0)
    expect(calculateGarbage(1, 4)).toBe(0)
  })

  it('follows the classic triangular chain table', () => {
    // chain 2→1, 3→3, 4→6, 5→10 (4 puyos cleared → no bonus).
    expect(calculateGarbage(2, 4)).toBe(1)
    expect(calculateGarbage(3, 4)).toBe(3)
    expect(calculateGarbage(4, 4)).toBe(6)
    expect(calculateGarbage(5, 4)).toBe(10)
  })

  it('adds a bonus for extra puyos cleared', () => {
    // chain 2 with 10 puyos → 1 + (10-4) = 7
    expect(calculateGarbage(2, 10)).toBe(7)
  })

  it('caps at 45 units', () => {
    expect(calculateGarbage(10, 4)).toBe(45)
    expect(calculateGarbage(20, 4)).toBe(45)
    expect(calculateGarbage(10, 99)).toBe(45)
  })
})

describe('applyGarbageToGrid', () => {
  it('distributes 2 stones per unit at the base of the board', () => {
    const grid = createEmptyBoard()
    applyGarbageToGrid(grid, 2, () => 0) // always column 0
    const stones = grid.flat().filter((c) => c === GARBAGE_COLOR)
    expect(stones).toHaveLength(4)
    expect(grid[11][0]).toBe(GARBAGE_COLOR)
    expect(grid[10][0]).toBe(GARBAGE_COLOR)
    expect(grid[9][0]).toBe(GARBAGE_COLOR)
    expect(grid[8][0]).toBe(GARBAGE_COLOR)
  })

  it('is deterministic when given a seeded rng', () => {
    const a = createEmptyBoard()
    const b = createEmptyBoard()
    let x = 0
    const rngA = () => {
      x = (x + 1) % 6
      return x / 6
    }
    const rngB = () => {
      x = (x + 1) % 6
      return x / 6
    }
    applyGarbageToGrid(a, 3, rngA)
    applyGarbageToGrid(b, 3, rngB)
    expect(a).toEqual(b)
  })

  it('pushes up into the top row when a column is full', () => {
    const grid = createEmptyBoard()
    for (let y = 0; y < 12; y++) grid[y][0] = 1 // column 0 full
    applyGarbageToGrid(grid, 1, () => 0)
    // The stone is NOT lost — it lands at the top, creating top-out pressure.
    expect(grid[0][0]).toBe(GARBAGE_COLOR)
  })

  it('does not error when the board is completely full', () => {
    const grid = createEmptyBoard()
    for (let y = 0; y < 12; y++) for (let x = 0; x < 6; x++) grid[y][x] = 1
    expect(() => applyGarbageToGrid(grid, 3, () => 0)).not.toThrow()
  })
})
