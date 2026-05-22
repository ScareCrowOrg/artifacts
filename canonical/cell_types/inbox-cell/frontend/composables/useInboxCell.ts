/**
 * @file useInboxCell.ts
 * @description Composable that encapsulates InboxCell.execute() calls with
 * reactive state for loading, error, messages, and requests.
 */

import { ref, readonly } from 'vue'
import { InboxCell } from '../InboxCell'

export function useInboxCell() {
  const cell = new InboxCell()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const messages = ref<any[]>([])
  const requests = ref<any[]>([])

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

  async function loadRequests() {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({ action: 'list_requests' })
      if (result.success) {
        requests.value = Array.isArray(result.output) ? result.output : []
      } else {
        error.value = result.error || 'Failed to load requests'
      }
    } catch (e: any) {
      error.value = e.message || 'Failed to load requests'
    } finally {
      isLoading.value = false
    }
  }

  async function approveRequest(requestId: string) {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({ action: 'approve_request', requestId })
      if (result.success) {
        const idx = requests.value.findIndex((r: any) => r._id === requestId)
        if (idx !== -1) {
          requests.value[idx] = { ...requests.value[idx], status: 'approved' }
        }
      } else {
        error.value = result.error || 'Failed to approve request'
      }
      return result.success
    } catch (e: any) {
      error.value = e.message || 'Failed to approve request'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function rejectRequest(requestId: string) {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({ action: 'reject_request', requestId })
      if (result.success) {
        const idx = requests.value.findIndex((r: any) => r._id === requestId)
        if (idx !== -1) {
          requests.value[idx] = { ...requests.value[idx], status: 'rejected' }
        }
      } else {
        error.value = result.error || 'Failed to reject request'
      }
      return result.success
    } catch (e: any) {
      error.value = e.message || 'Failed to reject request'
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function replyToMessage(targetUserId: string, subject: string, body: string) {
    isLoading.value = true
    error.value = null
    try {
      const result = await cell.execute({
        action: 'reply_to_message',
        targetUserId,
        subject,
        body,
      })
      if (!result.success) {
        error.value = result.error || 'Failed to reply to message'
      }
      return result.success
    } catch (e: any) {
      error.value = e.message || 'Failed to reply to message'
      return false
    } finally {
      isLoading.value = false
    }
  }

  return {
    isLoading: readonly(isLoading),
    error: readonly(error),
    messages: readonly(messages),
    requests: readonly(requests),
    loadMessages,
    loadRequests,
    approveRequest,
    rejectRequest,
    replyToMessage,
  }
}
