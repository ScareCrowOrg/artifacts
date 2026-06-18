/**
 * Generic Toast Notification Composable
 *
 * Provides a reusable toast notification system for cells.
 * Manages toastMessage ref, toastType ref, and auto-dismiss timer.
 *
 * Usage:
 * ```ts
 * const { toastMessage, toastType, showToast } = useToast()
 *
 * // Show a success toast
 * showToast('Your request has been submitted!', 'success')
 *
 * // Show an error toast
 * showToast('Something went wrong', 'error')
 * ```
 *
 * Template (must be added to each component that uses it):
 * ```html
 * <div v-if="toastMessage"
 *      class="fixed bottom-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm text-white transition-opacity duration-300"
 *      :class="toastType === 'success' ? 'bg-green-600' : 'bg-red-600'">
 *   {{ toastMessage }}
 * </div>
 * ```
 *
 * @module useToast
 */
import { ref, type Ref } from 'vue'

export interface UseToastReturn {
  /** Current toast message text, null when hidden */
  toastMessage: Ref<string | null>
  /** Toast type for styling: 'success' (green) or 'error' (red) */
  toastType: Ref<'success' | 'error'>
  /** Show a toast notification. Auto-hides after 3 seconds. */
  showToast: (message: string, type?: 'success' | 'error') => void
}

/**
 * Creates a toast notification state with auto-dismiss.
 * Each call creates an independent toast instance — use in any component.
 */
export function useToast(): UseToastReturn {
  const toastMessage = ref<string | null>(null)
  const toastType = ref<'success' | 'error'>('success')
  let toastTimer: ReturnType<typeof setTimeout> | null = null

  function showToast(message: string, type: 'success' | 'error' = 'success') {
    toastMessage.value = message
    toastType.value = type
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => {
      toastMessage.value = null
    }, 3000)
  }

  return {
    toastMessage,
    toastType,
    showToast,
  }
}
