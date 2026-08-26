/**
 * @file puyoStore.ts
 * @description Pinia store for puyo-party-cell — the server-authoritative game
 * state.
 *
 * Holds a single distributed branch ``game`` (lww) synchronised via
 * ``useDistributedState`` from the Redis channel ``puyo:game:{roomId}``.  The
 * backend ``main.py`` is the ONLY writer: it publishes snapshot envelopes that
 * the WSS router (forward-only) forwards to every client; this store never
 * mutates the branch directly — it only RECEIVES snapshots and exposes
 * read helpers for the View.
 *
 * ``usePuyoRealtime()`` wires the branch to the channel (like
 * ``useGameRealtime`` in party-game).  It must run inside a component setup
 * (uses lifecycle hooks via useDistributedState).
 */

import { defineStore } from 'pinia'
import { computed, ref, type ComputedRef } from 'vue'
import { useDistributedState } from '#artifacts/shared/composables/useDistributedState'
import { usePartyStore } from '#artifacts/shared/stores/partyStore'

// ── Types ───────────────────────────────────────────────────────────────────

export type PuyoGameStatus = 'waiting' | 'running' | 'game_over'

export interface PuyoGameOver {
  winnerId: string
  reason: string
}

export interface PuyoGameState {
  status: PuyoGameStatus
  /** Deterministic piece-sequence seed (null until start_game). */
  seed: number | null
  round: number
  scores: Record<string, number>
  readyFlags: Record<string, boolean>
  /** Garbage units pending delivery per participant (server-arbitrated). */
  garbagePending: Record<string, number>
  /** Last locked grid per participant (1-D 72-cell compact grids). */
  grids: Record<string, number[]>
  gameOver: PuyoGameOver | null
}

// ── Store ───────────────────────────────────────────────────────────────────

export const usePuyoStore = defineStore('puyoParty', () => {
  /** Server-authoritative game snapshot (branch ``game``, lww). */
  const game = ref<PuyoGameState | null>(null)

  /** Reset local branches (room switch / leave / new game). */
  function reset(): void {
    game.value = null
  }

  return { game, reset }
})

// ── Realtime sync (must run inside a component setup) ──────────────────────

/**
 * Wire the ``game`` branch to the Redis channel ``puyo:game:{roomId}``.
 * Reconnects automatically when ``partyStore.currentRoom`` changes.  The
 * backend is the only writer; this composable only RECEIVES snapshots.
 */
export function usePuyoRealtime(): { gameConnected: ComputedRef<boolean> } {
  const store = usePuyoStore()
  const partyStore = usePartyStore()

  const roomCtx = computed(() => (partyStore.currentRoom ? `puyo:game:${partyStore.currentRoom}` : ''))

  const gameSync = useDistributedState({
    contextId: roomCtx,
    store: store as unknown as Record<string, unknown>,
    branch: 'game',
    conflictStrategy: 'lww',
  })

  const gameConnected = computed(() => Boolean(gameSync.isConnected.value))

  return { gameConnected }
}

// ── Read helpers (1v1) ──────────────────────────────────────────────────────

/**
 * Opponent participant id in the current 1v1 match, or null.  The opponent is
 * the running participant that is not ``myId`` (falls back to any other
 * participant id that has a grid).
 */
export function opponentId(game: PuyoGameState | null, myId: string | null): string | null {
  if (!game || !myId) return null
  const ids = Object.keys(game.grids ?? {})
  const other = ids.find((id) => id !== myId)
  return other ?? null
}

/** The opponent's last locked grid (1-D 72 cells), or null when not started. */
export function remoteGridOf(game: PuyoGameState | null, myId: string | null): number[] | null {
  const opponent = opponentId(game, myId)
  if (!opponent) return null
  return game?.grids?.[opponent] ?? null
}
