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
  /**
   * Room identifier (without the `planet-chat:` prefix).
   * Used as the `contextId` in POST requests to execute-ephemeral.
   * The backend will publish to `planet-chat:{roomId}`.
   *
   * Accepts a plain string or a `Ref<string>` so the composable stays
   * in sync when the room changes (e.g. after switchRoom).
   */
  roomId: string | { readonly value: string }

  /** Current authenticated user / sender identifier */
  senderId?: string
}

export function usePlanetChat(options: UsePlanetChatOptions) {
  const { senderId } = options

  /** Resolve the current roomId, supporting both plain strings and reactive refs.
   * Functions that call this (`sendMessage`, `requestSnapshot`) use the value
   * at call-time — they do not establish reactive dependencies. */
  function getRoomId(): string {
    return typeof options.roomId === 'string' ? options.roomId : options.roomId.value
  }

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
   * senderId is omitted from the payload when not explicitly provided so
   * that the backend can inject the authenticated user_id from the session.
   *
   * @returns `true` on success, `false` on failure.
   */
  async function sendMessage(text: string): Promise<boolean> {
    const trimmed = text.trim()
    if (!trimmed) return false

    isSending.value = true
    sendError.value = null

    // [DEBUG planet-chat B2] Log senderId and contextId at send time
    console.log('[usePlanetChat][DEBUG] sendMessage — roomId:', getRoomId(), 'senderId:', senderId, 'text length:', trimmed.length)

    try {
      const payload: Record<string, unknown> = {
        action: 'send_message',
        contextId: getRoomId(),
        message: trimmed,
        timestamp: Date.now(),
      }
      // Only include senderId when explicitly provided; omitting it allows the
      // backend to inject the authenticated user_id from the session cookie.
      if (senderId !== undefined) {
        payload.senderId = senderId
      }

      const result = await cell.execute(payload)

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
      const payload: Record<string, unknown> = {
        action: 'snapshot_request',
        contextId: getRoomId(),
      }
      if (senderId !== undefined) {
        payload.senderId = senderId
      }
      await cell.execute(payload)
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
