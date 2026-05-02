/**
 * @file planetChat.ts
 * @description Pinia store for planet-chat-cell.
 *
 * Manages local chat state:
 *   - messages:  append-only history, synchronised via useDistributedState
 *   - typing:    per-sender typing indicators (LWW)
 *   - partyId:   current context / party identifier
 *
 * The store is intentionally thin — most mutation logic lives in
 * useDistributedState (JSON Patch application) and usePlanetChat
 * (user-facing actions).
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  /** Unique identifier: "{timestamp}-{senderId}" */
  id: string

  /** Plain-text message content */
  text: string

  /** User / agent identifier */
  senderId: string

  /** Unix timestamp in milliseconds */
  timestamp: number
}

export interface TypingIndicator {
  /** Sender who is currently typing */
  senderId: string

  /** Unix timestamp of the last typing event (ms) */
  timestamp: number
}

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

export const usePlanetChatStore = defineStore('planetChat', () => {
  // ── State ─────────────────────────────────────────────────────────────────

  /** Ordered message history.  Append-only — never remove or reorder. */
  const messages = ref<ChatMessage[]>([])

  /** Per-sender typing indicators.  Keyed by senderId. */
  const typing = ref<Record<string, TypingIndicator>>({})

  /** Active context / party identifier */
  const partyId = ref<string | null>(null)

  /** Whether the initial snapshot has been received from the server */
  const isHydrated = ref(false)

  // ── Actions ───────────────────────────────────────────────────────────────

  /**
   * Add a message to the local history.
   * Deduplicates by `id` to prevent double-rendering when the local mutation
   * echo arrives via WebSocket.
   */
  function addMessage(msg: ChatMessage): void {
    if (messages.value.some((m) => m.id === msg.id)) return
    messages.value.push(msg)
  }

  /**
   * Replace the full message history (called when snapshot is received).
   */
  function setMessages(msgs: ChatMessage[]): void {
    messages.value = [...msgs]
    isHydrated.value = true
  }

  /**
   * Update or remove a typing indicator for a sender.
   * Pass `null` to remove the indicator (sender stopped typing).
   */
  function setTyping(senderId: string, indicator: TypingIndicator | null): void {
    if (indicator === null) {
      const copy = { ...typing.value }
      delete copy[senderId]
      typing.value = copy
    } else {
      typing.value = { ...typing.value, [senderId]: indicator }
    }
  }

  /**
   * Reset the store to its initial state.
   * Called when the cell is unmounted or the partyId changes.
   */
  function reset(): void {
    messages.value = []
    typing.value = {}
    isHydrated.value = false
  }

  // ── Getters ───────────────────────────────────────────────────────────────

  /** Sorted message history (chronological) */
  function sortedMessages(): ChatMessage[] {
    return [...messages.value].sort((a, b) => a.timestamp - b.timestamp)
  }

  /** List of senders who are actively typing */
  function typingSenders(): string[] {
    return Object.keys(typing.value)
  }

  return {
    // state
    messages,
    typing,
    partyId,
    isHydrated,
    // actions
    addMessage,
    setMessages,
    setTyping,
    reset,
    // getters
    sortedMessages,
    typingSenders,
  }
})
