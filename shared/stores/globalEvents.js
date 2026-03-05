// Global Events Store for cell creation via copy-to-manual
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useGlobalEventsStore = defineStore('globalEvents', () => {
  // State: holds the last copied content for cell creation
  const copiedContent = ref(null)

  // Action: set copied content (triggers cell creation)
  function setCopiedContent(content) {
    copiedContent.value = content
  }

  // Action: clear copied content (after cell is created)
  function clearCopiedContent() {
    copiedContent.value = null
  }

  return {
    copiedContent,
    setCopiedContent,
    clearCopiedContent,
  }
})
