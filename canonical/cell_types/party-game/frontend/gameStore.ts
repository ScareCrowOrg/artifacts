/**
 * @file gameStore.ts
 * @description Pinia store for party-game — the drawing/guessing game state.
 *
 * Holds the 3 distributed branches synchronised via `useDistributedState`:
 *   - `game`    (lww)     ← server-authoritative snapshots from the backend
 *   - `strokes` (append)  ← committed drawing strokes (canvas)
 *   - `guesses` (append)  ← guess / hint / system feed
 *
 * The store is intentionally thin: the BACKEND is the only writer to the game
 * channels (the WSS router is forward-only), so this store never mutates its
 * branches directly — it only RECEIVES snapshots/patches and exposes actions
 * for the View to read state.
 *
 * `useGameRealtime()` wires the 3 game branches PLUS the shared party presence
 * branch (`partyStore.participants`, channel `calls:room:{roomId}`) so the
 * roster reuses the party presence contract.  It must be called inside a
 * component setup (it uses lifecycle hooks via useDistributedState).
 */

import { defineStore } from 'pinia'
import { computed, ref, type ComputedRef } from 'vue'
import { useDistributedState } from '#artifacts/shared/composables/useDistributedState'
import { usePartyStore } from '#artifacts/shared/stores/partyStore'

// ── Types ───────────────────────────────────────────────────────────────────

export type GamePhase = 'lobby' | 'draw' | 'guess' | 'reveal' | 'finished'

export interface PlayerInfo {
  participantId: string
  displayName: string
}

export interface GameState {
  round: number
  totalRounds: number
  phase: GamePhase
  drawerId: string | null
  drawerName: string | null
  category: string | null
  hintCount: number
  wrongCount: number
  scores: Record<string, number>
  roundWinners: string[]
  players: PlayerInfo[]
}

export interface Point2D {
  x: number
  y: number
}

export interface Stroke {
  id?: string
  tool: 'pen' | 'eraser'
  color: string
  width: number
  points: Point2D[]
}

export type GuessType = 'guess' | 'hint' | 'system'

export interface GuessMessage {
  id: string
  userId: string
  displayName: string
  text: string
  type: GuessType
  isCorrect?: boolean
}

// ── Store ───────────────────────────────────────────────────────────────────

export const useGameStore = defineStore('partyGame', () => {
  /** Server-authoritative game state (round/phase/drawer/scores). */
  const game = ref<GameState | null>(null)

  /** Committed drawing strokes for the current round. */
  const strokes = ref<Stroke[]>([])

  /** Guess / hint / system feed. */
  const guesses = ref<GuessMessage[]>([])

  /** Reset local branches (room switch / new game session). */
  function reset(): void {
    game.value = null
    strokes.value = []
    guesses.value = []
  }

  return { game, strokes, guesses, reset }
})

// ── Realtime sync (must run inside a component setup) ──────────────────────

/**
 * Wire the game's 3 branches + the shared party presence to their Redis
 * channels.  Called once from View.vue's setup.  The channel prefixes follow
 * the backend: `game:room:{roomId}:state|strokes|guesses` and
 * `calls:room:{roomId}` (presence).
 */
export function useGameRealtime(): {
  /** Combined "all 3 game branches connected" signal for the header. */
  stateConnected: ComputedRef<boolean>
} {
  const store = useGameStore()
  const partyStore = usePartyStore()

  const roomCtx = computed(() => (partyStore.currentRoom ? `game:room:${partyStore.currentRoom}` : ''))
  const presenceCtx = computed(() => (partyStore.currentRoom ? `calls:room:${partyStore.currentRoom}` : ''))

  const stateSync = useDistributedState({
    contextId: computed(() => (roomCtx.value ? `${roomCtx.value}:state` : '')),
    store: store as unknown as Record<string, unknown>,
    branch: 'game',
    conflictStrategy: 'lww',
  })

  const strokesSync = useDistributedState({
    contextId: computed(() => (roomCtx.value ? `${roomCtx.value}:strokes` : '')),
    store: store as unknown as Record<string, unknown>,
    branch: 'strokes',
    conflictStrategy: 'append',
  })

  const guessesSync = useDistributedState({
    contextId: computed(() => (roomCtx.value ? `${roomCtx.value}:guesses` : '')),
    store: store as unknown as Record<string, unknown>,
    branch: 'guesses',
    conflictStrategy: 'append',
  })

  const presenceSync = useDistributedState({
    contextId: presenceCtx,
    store: partyStore as unknown as Record<string, unknown>,
    branch: 'participants',
    conflictStrategy: 'append',
  })

  // Expose a combined "all game branches connected" signal for the header.
  // presenceSync is wired for partyStore.participants but not surfaced here —
  // the roster connection state is not displayed.
  const stateConnected = computed(
    () => Boolean(stateSync.isConnected.value) && Boolean(strokesSync.isConnected.value) && Boolean(guessesSync.isConnected.value),
  )

  return { stateConnected }
}
