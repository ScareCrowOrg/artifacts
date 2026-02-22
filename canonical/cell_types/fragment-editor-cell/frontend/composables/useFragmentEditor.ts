/**
 * @file useFragmentEditor.ts
 * @description Composable for fragment editing logic
 * 
 * This composable provides reactive state and methods for fragment editing
 * operations within the Fragment Editor Cell.
 */

import { ref, computed } from 'vue'
import type { FragmentEditorCell } from '../FragmentEditorCell'

/**
 * Composable for fragment editing
 * 
 * @param cellInstance - FragmentEditorCell instance
 * @returns Reactive state and methods for fragment editing
 */
export function useFragmentEditor(cellInstance: FragmentEditorCell) {
  const content = ref('')
  const saving = ref(false)
  const error = ref('')
  const success = ref('')
  
  /**
   * Check if content is valid (not empty)
   */
  const isValid = computed(() => content.value.trim().length > 0)
  
  /**
   * Save fragment with given input
   * 
   * @param input - Fragment editor input parameters
   * @returns Promise resolving to cell result
   */
  async function save(input: Record<string, any>) {
    saving.value = true
    error.value = ''
    success.value = ''
    
    try {
      const result = await cellInstance.execute({
        ...input,
        content: content.value
      })
      
      if (!result.success) {
        error.value = result.error || 'Save failed'
        return result
      }
      
      success.value = result.output?.message || 'Fragment saved successfully'
      return result
    } catch (err: any) {
      error.value = err.message || 'An error occurred'
      throw err
    } finally {
      saving.value = false
    }
  }
  
  /**
   * Load fragment content
   * 
   * @param fragmentId - Fragment ID to load
   * @returns Promise resolving to cell result
   */
  async function load(fragmentId: string) {
    saving.value = true
    error.value = ''
    
    try {
      const result = await cellInstance.execute({
        action: 'load',
        fragmentId
      })
      
      if (result.success && result.output?.content) {
        content.value = result.output.content
      } else {
        error.value = result.error || 'Failed to load fragment'
      }
      
      return result
    } catch (err: any) {
      error.value = err.message || 'An error occurred'
      throw err
    } finally {
      saving.value = false
    }
  }
  
  /**
   * Clear all messages
   */
  function clearMessages() {
    error.value = ''
    success.value = ''
  }
  
  /**
   * Reset to initial state
   */
  function reset() {
    content.value = ''
    saving.value = false
    error.value = ''
    success.value = ''
  }
  
  return {
    // State
    content,
    saving,
    error,
    success,
    isValid,
    
    // Methods
    save,
    load,
    clearMessages,
    reset
  }
}
