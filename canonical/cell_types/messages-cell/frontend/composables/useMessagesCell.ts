/**
 * @file useMessagesCell.ts
 * @description Composable that encapsulates MessagesCell.execute() calls with
 * reactive state for loading, error, and messages.
 */

import { ref, readonly } from 'vue'
import { MessagesCell } from '../MessagesCell'

export function useMessagesCell() {
  const cell = new MessagesCell()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const messages = ref<any[]>([])

  async function loadMessages() {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({ action: 'list_messages' })
      if (result.success) {
        messages.value = Array.isArray(result.output) ? result.output : []
      } else {
        error.value = result.error || 'Failed to load messages'
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to load messages'
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading: readonly(isLoading),
    error: readonly(error),
    messages,
    loadMessages,
  }
}
