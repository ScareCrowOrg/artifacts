/**
 * @file PuyoGarbage.ts
 * @description Attack formula for the Puyo Party cell — pure TS, no Vue.
 *
 * The board-side garbage mechanics (stone count, distribution and the drop
 * rule) live in ``engine/PuyoBoard.ts`` (``applyGarbageToGrid`` /
 * ``garbageStoneCount``) — the SINGLE source of truth used by both the session
 * and the tests.  This module keeps the pure attack-power formula only.
 */

/**
 * Attack power of a chain: how many garbage UNITS to send the opponent.
 *
 * Uses the classic Puyo Puyo chain table (triangular numbers: 1, 3, 6, 10,
 * 15, … for chains 2, 3, 4, …) plus a small bonus for clearing more puyos
 * than the bare minimum.  Capped at 45 units so a single attack never
 * instantly tops out a 6×12 board (45 units = 90 stones).
 *
 * @param chain        Number of chain steps (0/1 → no attack).
 * @param totalCleared Colored puyos cleared across the chain (bonus term).
 */
export function calculateGarbage(chain: number, totalCleared: number): number {
  if (chain <= 1) return 0
  const base = Math.floor(((chain - 1) * chain) / 2)
  const bonus = Math.max(0, totalCleared - 4)
  return Math.min(45, base + bonus)
}
