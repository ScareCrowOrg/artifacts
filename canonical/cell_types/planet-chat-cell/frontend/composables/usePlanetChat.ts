/**
 * @file usePlanetChat.ts
 * @description Composable providing user-facing chat actions for planet-chat-cell.
 *
 * Wraps PlanetChatCell.execute() with reactive state for pending / error
 * conditions, and exposes a clean `sendMessage` function to View.vue.
 *
 * Responsibilities
 * ----------------
 * - Provide `sendMessage(text)` — calls PlanetChatCell.execute() with the
 *   configured `contextId` and returns the result.
 * - Track `isSending` (loading state) and `sendError` (last error).
 * - Provide `requestSnapshot()` — asks the backend to re-publish the current
 *   message history on the channel.
 *
 * Not responsible for
 * -------------------
 * - WebSocket connection / distributed state sync → handled by useDistributedState
 * - Store mutations from remote patches → handled by useDistributedState
 */

import { ref } from 'vue'
import { PlanetChatCell } from '../PlanetChatCell'

export interface UsePlanetChatOptions {
  /** Context / party identifier used to scope the Redis channel */
  contextId: string

  /** Current authenticated user / sender identifier */
  senderId?: string
}

export function usePlanetChat(options: UsePlanetChatOptions) {
  const { contextId, senderId = 'anonymous' } = options

  const cell = new PlanetChatCell()

  const isSending = ref(false)
  const sendError = ref<string | null>(null)

  /**
   * Send a new chat message.
   *
   * Calls PlanetChatCell.execute() which POSTs to execute-ephemeral.
   * The backend then PUBLISHes the patch to Redis; all connected clients
   * (including the sender) receive the update via WebSocket.
   *
   * @returns `true` on success, `false` on failure.
   */
  async function sendMessage(text: string): Promise<boolean> {
    const trimmed = text.trim()
    if (!trimmed) return false

    isSending.value = true
    sendError.value = null

    try {
      const result = await cell.execute({
        action: 'send_message',
        contextId,
        message: trimmed,
        senderId,
        timestamp: Date.now(),
      })

      if (!result.success) {
        sendError.value = result.error ?? 'Failed to send message'
        return false
      }

      return true
    } catch (err: unknown) {
      sendError.value = err instanceof Error ? err.message : 'Unexpected error'
      return false
    } finally {
      isSending.value = false
    }
  }

  /**
   * Request the server to re-publish the current snapshot on the channel.
   *
   * Useful when the WebSocket reconnects or when the component mounts and
   * useDistributedState's automatic snapshot_request may not have been
   * acknowledged yet.
   */
  async function requestSnapshot(): Promise<void> {
    try {
      await cell.execute({
        action: 'snapshot_request',
        contextId,
        senderId,
      })
    } catch {
      // Non-critical: useDistributedState will retry on next reconnect
    }
  }

  return {
    isSending,
    sendError,
    sendMessage,
    requestSnapshot,
  }
}
