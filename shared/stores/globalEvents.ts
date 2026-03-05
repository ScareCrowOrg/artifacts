/**
 * Global Events Store
 * 
 * Manages global events for cell creation via copy-to-manual functionality.
 * 
 * @module stores/globalEvents
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Global Events Store
 */
export const useGlobalEventsStore = defineStore('globalEvents', () => {
  // State: holds the last copied content for cell creation
  const copiedContent = ref<string | null>(null)

  /**
   * Set copied content (triggers cell creation)
   * @param content - Content to copy
   */
  function setCopiedContent(content: string | null): void {
    copiedContent.value = content
  }

  /**
   * Clear copied content (after cell is created)
   */
  function clearCopiedContent(): void {
    copiedContent.value = null
  }

  return {
    copiedContent,
    setCopiedContent,
    clearCopiedContent,
  }
})
