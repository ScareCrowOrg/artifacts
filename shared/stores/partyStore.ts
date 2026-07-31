/**
 * @file partyStore.ts
 * @description Pinia store for party / room presence in Cloudflare Calls.
 *
 * Manages room participant state:
 *   - participants: list of active room members, synchronised via
 *                   useDistributedState (JSON Patch, LWW conflict strategy)
 *   - currentRoom:  active room identifier
 *   - isHydrated:   whether the initial snapshot has been received
 *
 * The store is intentionally thin — most mutation logic lives in
 * useDistributedState (patch application) and usePartyCalls
 * (user-facing actions).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type TrackType = 'mic' | 'camera' | 'screen'

export interface Participant {
  /** Unique participant identifier (typically the user's id) */
  participantId: string

  /** Cloudflare Calls session id — used to associate remote media streams */
  sessionId?: string

  /** Human-readable display name */
  displayName: string

  /** Media tracks the participant is currently publishing */
  tracks: TrackType[]

  /** Whether the participant's audio is muted */
  isMuted: boolean

  /** Unix timestamp in milliseconds when the participant joined */
  joinedAt: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

export const usePartyStore = defineStore('party', () => {
  // ── State ─────────────────────────────────────────────────────────────────

  /** Active room participants.  Synchronised via useDistributedState. */
  const participants = ref<Participant[]>([])

  /** Current room identifier (e.g. 'planet-lobby' or 'room:{roomId}') */
  const currentRoom = ref<string | null>(null)

  /** Whether the initial snapshot has been received from the server */
  const isHydrated = ref(false)

  // ── Actions ───────────────────────────────────────────────────────────────

  /**
   * Replace the full participant list (called when snapshot is received
   * from useDistributedState).
   */
  function setParticipants(list: Participant[]): void {
    participants.value = list
    isHydrated.value = true
  }

  /**
   * Add a single participant to the local list.
   * Deduplicates by participantId to prevent double-rendering when the
   * local mutation echo arrives via WebSocket.
   */
  function addParticipant(p: Participant): void {
    if (participants.value.some((existing) => existing.participantId === p.participantId)) {
      return
    }
    participants.value.push(p)
  }

  /**
   * Remove a participant by id (called when someone leaves the room).
   */
  function removeParticipant(id: string): void {
    participants.value = participants.value.filter((p) => p.participantId !== id)
  }

  /**
   * Update specific fields on an existing participant (e.g. mute toggle,
   * track change) without replacing the full list.
   */
  function updateParticipant(id: string, data: Partial<Participant>): void {
    const idx = participants.value.findIndex((p) => p.participantId === id)
    if (idx === -1) return
    participants.value[idx] = { ...participants.value[idx], ...data }
  }

  /**
   * Reset the store to its initial state.
   * Called when the room changes or the call ends.
   */
  function reset(): void {
    participants.value = []
    currentRoom.value = null
    isHydrated.value = false
  }

  return {
    // state
    participants,
    currentRoom,
    isHydrated,
    // actions
    setParticipants,
    addParticipant,
    removeParticipant,
    updateParticipant,
    reset,
  }
})
