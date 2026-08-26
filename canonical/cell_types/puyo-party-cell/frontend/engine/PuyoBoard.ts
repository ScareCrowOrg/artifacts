/**
 * @file PuyoBoard.ts
 * @description Deterministic Puyo Puyo board engine — pure TS, no Vue.
 *
 * Owns the 6×12 grid, piece mechanics (spawn / move / rotate / drop / lock),
 * gravity, BFS group detection (≥4 same color), chain resolution (cascading
 * clears with garbage removal) and top-out detection.  ``PuyoSession`` ties a
 * board + ``PuyoRNG`` + current piece + garbage queue together so the View can
 * run the whole local simulation with zero network latency.
 *
 * The engine is fully deterministic given a seed: every client that receives
 * the same seed simulates the SAME piece sequence (lockstep).  Garbage
 * placement uses a SEPARATE seeded RNG (not the piece RNG) so garbage amounts
 * never perturb the shared piece queue.
 */

import { mulberry32, PuyoRNG, type PuyoPair } from './PuyoRNG'

export const BOARD_WIDTH = 6
export const BOARD_HEIGHT = 12
/** Empty cell marker. */
export const EMPTY = 0
/** Garbage puyo marker (colorless junk cleared by chains). */
export const GARBAGE_COLOR = 5
/** Horizontal spawn anchor for the leading puyo of a new piece. */
export const SPAWN_X = Math.floor((BOARD_WIDTH - 2) / 2)
/** Vertical spawn anchor (top row). */
export const SPAWN_Y = 0

/** A 6×12 grid of cell ids (0 empty, 1..4 colors, 5 garbage). */
export type BoardGrid = number[][]

export type Rotation = 0 | 1 | 2 | 3

export interface PuyoPiece {
  /** Leading puyo color (pivot). */
  a: number
  /** Trailing puyo color. */
  b: number
  /** Anchor column (leading puyo). */
  x: number
  /** Anchor row (leading puyo). */
  y: number
  rotation: Rotation
}

export interface LockResult {
  /** Post-resolution grid (clone — read-only snapshot of the session board). */
  board: BoardGrid
  /** Number of chain steps executed (0 = no clear, 1 = single clear). */
  chains: number
  /** Number of colored puyos cleared across all chain steps (excl. garbage). */
  totalCleared: number
}

/** Second-puyo offset relative to the anchor per rotation (clockwise cycle). */
const ROTATION_OFFSETS: ReadonlyArray<readonly [number, number]> = [
  [0, 1], // rot 0: trailing below the leading puyo
  [1, 0], // rot 1: trailing right of the leading puyo
  [0, -1], // rot 2: trailing above the leading puyo
  [-1, 0], // rot 3: trailing left of the leading puyo
]

const DIRS: ReadonlyArray<readonly [number, number]> = [
  [0, 1],
  [0, -1],
  [1, 0],
  [-1, 0],
]

// ── Grid helpers ─────────────────────────────────────────────────────────────

export function createEmptyBoard(): BoardGrid {
  return Array.from({ length: BOARD_HEIGHT }, () => Array<number>(BOARD_WIDTH).fill(EMPTY))
}

export function cloneBoard(board: BoardGrid): BoardGrid {
  return board.map((row) => row.slice())
}

export function inBounds(x: number, y: number): boolean {
  return x >= 0 && x < BOARD_WIDTH && y >= 0 && y < BOARD_HEIGHT
}

/** Flatten a grid to a 1-D array (payload of ``piece_locked``). */
export function compactGrid(board: BoardGrid): number[] {
  return board.flat()
}

/** Parse a 1-D array (or raw rows) back into a validated 6×12 grid. */
export function parseGrid(data: number[] | number[][], width = BOARD_WIDTH, height = BOARD_HEIGHT): BoardGrid {
  if (Array.isArray(data) && data.length > 0 && Array.isArray(data[0])) {
    const rows = data as number[][]
    const grid = createEmptyBoard()
    for (let y = 0; y < height && y < rows.length; y++) {
      for (let x = 0; x < width && x < rows[y].length; x++) {
        grid[y][x] = normalizeCell(rows[y][x])
      }
    }
    return grid
  }
  const flat = data as number[]
  const grid = createEmptyBoard()
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      grid[y][x] = normalizeCell(flat[y * width + x])
    }
  }
  return grid
}

function normalizeCell(value: number): number {
  return Number.isFinite(value) && value >= EMPTY && value <= GARBAGE_COLOR ? Math.trunc(value) : EMPTY
}

// ── Piece mechanics ──────────────────────────────────────────────────────────

/** The two cells a piece occupies: [leading (color a), trailing (color b)]. */
export function pieceCells(piece: PuyoPiece): Array<[number, number]> {
  const [dx, dy] = ROTATION_OFFSETS[piece.rotation]
  return [
    [piece.x, piece.y],
    [piece.x + dx, piece.y + dy],
  ]
}

export function canPlace(board: BoardGrid, piece: PuyoPiece): boolean {
  for (const [x, y] of pieceCells(piece)) {
    if (!inBounds(x, y)) return false
    if (board[y][x] !== EMPTY) return false
  }
  return true
}

/** A piece spawned from the RNG queue (anchor at the spawn column). */
export function spawnPiece(rng: PuyoRNG): PuyoPiece {
  const pair: PuyoPair = rng.pair()
  return { a: pair.a, b: pair.b, x: SPAWN_X, y: SPAWN_Y, rotation: 0 }
}

/** Shift a piece by (dx, dy); returns null when the move collides. */
export function movePiece(board: BoardGrid, piece: PuyoPiece, dx: number, dy: number): PuyoPiece | null {
  const candidate = { ...piece, x: piece.x + dx, y: piece.y + dy }
  return canPlace(board, candidate) ? candidate : null
}

/** Rotate a piece with simple wall kicks; returns the original when blocked. */
export function rotatePiece(board: BoardGrid, piece: PuyoPiece, dir: 1 | -1): PuyoPiece {
  const rotation = ((piece.rotation + dir + 4) % 4) as Rotation
  for (const kick of [0, -1, 1]) {
    const candidate = { ...piece, rotation, x: piece.x + kick }
    if (canPlace(board, candidate)) return candidate
  }
  return piece
}

/** Lowest row the piece can reach before colliding. */
export function dropY(board: BoardGrid, piece: PuyoPiece): number {
  let y = piece.y
  while (canPlace(board, { ...piece, y: y + 1 })) y += 1
  return y
}

/** Teleport a piece to the bottom of its column (hard drop). */
export function hardDrop(board: BoardGrid, piece: PuyoPiece): PuyoPiece {
  return { ...piece, y: dropY(board, piece) }
}

/** True when a freshly spawned piece cannot fit — the board has topped out. */
export function spawnAreaBlocked(board: BoardGrid): boolean {
  const probe: PuyoPiece = { a: 1, b: 1, x: SPAWN_X, y: SPAWN_Y, rotation: 0 }
  return !canPlace(board, probe)
}

// ── Gravity ──────────────────────────────────────────────────────────────────

/** Drop every cell to the bottom of its column (preserves horizontal order). */
export function applyGravity(board: BoardGrid): BoardGrid {
  const next = createEmptyBoard()
  for (let x = 0; x < BOARD_WIDTH; x++) {
    let write = BOARD_HEIGHT - 1
    for (let y = BOARD_HEIGHT - 1; y >= 0; y--) {
      const cell = board[y][x]
      if (cell !== EMPTY) {
        next[write][x] = cell
        write -= 1
      }
    }
  }
  return next
}

// ── Chain detection (BFS ≥4) ─────────────────────────────────────────────────

/**
 * BFS group of same-colored cells starting at (startX, startY).
 * Returns the group only when it has ≥4 cells; otherwise null.
 * Garbage cells (GARBAGE_COLOR) are never part of a color group.
 */
export function findColorGroup(board: BoardGrid, startX: number, startY: number): Array<[number, number]> | null {
  const color = board[startY]?.[startX]
  if (color === undefined || color === EMPTY || color === GARBAGE_COLOR) return null
  const seen = new Set<string>([`${startX},${startY}`])
  const stack: Array<[number, number]> = [[startX, startY]]
  const group: Array<[number, number]> = []
  while (stack.length > 0) {
    const [x, y] = stack.pop() as [number, number]
    group.push([x, y])
    for (const [dx, dy] of DIRS) {
      const nx = x + dx
      const ny = y + dy
      const key = `${nx},${ny}`
      if (inBounds(nx, ny) && !seen.has(key) && board[ny][nx] === color) {
        seen.add(key)
        stack.push([nx, ny])
      }
    }
  }
  return group.length >= 4 ? group : null
}

/** All disjoint color groups with ≥4 cells on the board. */
export function findAllGroups(board: BoardGrid): Array<Array<[number, number]>> {
  const scanned = new Set<string>()
  const groups: Array<Array<[number, number]>> = []
  for (let y = 0; y < BOARD_HEIGHT; y++) {
    for (let x = 0; x < BOARD_WIDTH; x++) {
      const cell = board[y][x]
      if (cell === EMPTY || cell === GARBAGE_COLOR || scanned.has(`${x},${y}`)) continue
      const group = findColorGroup(board, x, y)
      if (!group) continue
      for (const [gx, gy] of group) scanned.add(`${gx},${gy}`)
      groups.push(group)
    }
  }
  return groups
}

/**
 * Resolve all chains: repeatedly clear groups ≥4 (plus garbage adjacent to the
 * cleared area — the standard Puyo cascade defense), apply gravity, and count
 * the steps.  Mutates nothing — returns a fresh board.
 */
export function resolveChains(board: BoardGrid): { board: BoardGrid; chains: number; totalCleared: number } {
  let current = cloneBoard(board)
  let chains = 0
  let totalCleared = 0

  for (;;) {
    const groups = findAllGroups(current)
    if (groups.length === 0) break

    const toClear = new Set<string>()
    for (const group of groups) {
      for (const [x, y] of group) toClear.add(`${x},${y}`)
      totalCleared += group.length
    }

    // Garbage 4-adjacent to the cleared area is pulled into the clear, and the
    // removal cascades (garbage can chain off garbage connected to the chain).
    let grew = true
    while (grew) {
      grew = false
      for (const key of Array.from(toClear)) {
        const [x, y] = key.split(',').map(Number) as [number, number]
        for (const [dx, dy] of DIRS) {
          const nx = x + dx
          const ny = y + dy
          if (inBounds(nx, ny) && current[ny][nx] === GARBAGE_COLOR && !toClear.has(`${nx},${ny}`)) {
            toClear.add(`${nx},${ny}`)
            grew = true
          }
        }
      }
    }

    for (const key of toClear) {
      const [x, y] = key.split(',').map(Number) as [number, number]
      current[y][x] = EMPTY
    }
    current = applyGravity(current)
    chains += 1
  }

  return { board: current, chains, totalCleared }
}

// ── Session (local deterministic simulation) ─────────────────────────────────

/**
 * A full local Puyo match: board + piece queue + garbage queue + score.
 * Two clients built from the same seed simulate the same game (lockstep).
 */
export class PuyoSession {
  readonly board: BoardGrid
  current: PuyoPiece
  nextPair: PuyoPair
  score: number
  /** Garbage units pending injection (arrives via the game snapshot). */
  garbageQueue: number
  /** Result of the most recent lock (chain info for piece_locked/submit_garbage). */
  lastLock: LockResult | null
  gameOver: boolean

  /** Piece queue RNG — the shared lockstep sequence. */
  private readonly spawnRng: PuyoRNG
  /** Separate RNG for garbage placement — never touches the piece queue. */
  private readonly garbageRng: () => number

  constructor(seed: number) {
    this.spawnRng = new PuyoRNG(seed)
    this.board = createEmptyBoard()
    const first = this.spawnRng.pair()
    this.current = { a: first.a, b: first.b, x: SPAWN_X, y: SPAWN_Y, rotation: 0 }
    this.nextPair = this.spawnRng.pair()
    this.garbageRng = mulberry32((seed ^ 0x9e3779b9) >>> 0)
    this.score = 0
    this.garbageQueue = 0
    this.lastLock = null
    this.gameOver = false
  }

  /** True when a new piece cannot spawn on the current board (top-out). */
  isTopOut(): boolean {
    return spawnAreaBlocked(this.board)
  }

  moveLeft(): boolean {
    const moved = movePiece(this.board, this.current, -1, 0)
    if (moved) this.current = moved
    return moved !== null
  }

  moveRight(): boolean {
    const moved = movePiece(this.board, this.current, 1, 0)
    if (moved) this.current = moved
    return moved !== null
  }

  rotate(dir: 1 | -1): void {
    this.current = rotatePiece(this.board, this.current, dir)
  }

  /**
   * Advance the falling piece one row.  Returns true when the piece locked
   * (chains resolved, next piece spawned).
   */
  tick(): boolean {
    const moved = movePiece(this.board, this.current, 0, 1)
    if (moved) {
      this.current = moved
      return false
    }
    this.lock()
    return true
  }

  /** Hard drop + lock immediately. */
  hardDrop(): void {
    this.current = hardDrop(this.board, this.current)
    this.lock()
  }

  /** Queue garbage units for injection on the next lock (client-local). */
  injectGarbage(amount: number): void {
    this.garbageQueue += Math.max(0, Math.floor(amount))
  }

  /** Lock the current piece, inject queued garbage, resolve chains, spawn next. */
  lock(): LockResult {
    const cells = pieceCells(this.current)
    for (let i = 0; i < cells.length; i++) {
      const [x, y] = cells[i]
      if (inBounds(x, y)) this.board[y][x] = i === 0 ? this.current.a : this.current.b
    }

    // Garbage drops at lock and can be cleared by the same chain resolution.
    // applyGarbageToGrid is the SINGLE source of truth for the drop rule (a
    // full column pushes up instead of silently discarding the stone).
    if (this.garbageQueue > 0) {
      applyGarbageToGrid(this.board, this.garbageQueue, this.garbageRng)
      this.garbageQueue = 0
    }

    const { board, chains, totalCleared } = resolveChains(this.board)
    for (let y = 0; y < BOARD_HEIGHT; y++) {
      for (let x = 0; x < BOARD_WIDTH; x++) this.board[y][x] = board[y][x]
    }

    const result: LockResult = { board: cloneBoard(board), chains, totalCleared }
    this.lastLock = result
    if (chains > 0) this.score += chains * 100 + totalCleared * 10

    this.current = { a: this.nextPair.a, b: this.nextPair.b, x: SPAWN_X, y: SPAWN_Y, rotation: 0 }
    this.nextPair = this.spawnRng.pair()
    if (this.isTopOut()) this.gameOver = true
    return result
  }

  /** Serialized grid (the payload sent via piece_locked). */
  serializeBoard(): number[] {
    return compactGrid(this.board)
  }
}

/** Two stones per garbage unit (classic Puyo Puyo). */
export function garbageStoneCount(amount: number): number {
  return Math.max(0, Math.floor(amount)) * 2
}

/**
 * Drop ``amount`` garbage units into the board as stones (2 per unit), stacked
 * at the base of random columns via gravity.  Uses a SEPARATE ``rng`` (never
 * the piece RNG) so garbage placement never perturbs the lockstep queue.
 */
export function applyGarbageToGrid(board: BoardGrid, amount: number, rng: () => number = Math.random): void {
  const stones = garbageStoneCount(amount)
  for (let i = 0; i < stones; i++) {
    dropGarbageStone(board, Math.floor(rng() * BOARD_WIDTH))
  }
}

function dropGarbageStone(board: BoardGrid, col: number): void {
  if (col < 0 || col >= BOARD_WIDTH) return
  for (let y = BOARD_HEIGHT - 1; y >= 0; y--) {
    if (board[y][col] === EMPTY) {
      board[y][col] = GARBAGE_COLOR
      return
    }
  }
  // Column full to the top → push a stone into the top row so the attack still
  // creates top-out pressure (it must never silently disappear).
  board[0][col] = GARBAGE_COLOR
}
