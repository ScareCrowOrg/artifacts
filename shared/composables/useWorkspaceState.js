import { ref, nextTick } from 'vue'

/**
 * Composable for managing workspace UI state
 * @returns {Object} Workspace state and methods
 */
export function useWorkspaceState() {
  const showSettings = ref(false)
  // showIssuesDashboard removed - migrated to issues-dashboard-cell
  // See: artifacts/canonical/cell_types/issues-dashboard-cell/
  const showManualCapture = ref(false)
  const showFileBrowser = ref(false)

  /**
   * Toggle settings panel
   */
  function toggleSettings() {
    showSettings.value = !showSettings.value
  }

  /**
   * Toggle issues dashboard
   * 
   * ⚠️ DEPRECATED: IssuesDashboard overlay has been migrated to issues-dashboard-cell
   * This function is kept for backward compatibility but should not be used.
   * 
   * TODO: Remove after confirming all consumers are updated
   * 
   * See: artifacts/canonical/cell_types/issues-dashboard-cell/
   */
  function toggleIssuesDashboard() {
    // No-op - cell should be launched via DynamicWorkspace instead
  }

  /**
   * Toggle manual capture and scroll to it
   */
  function toggleManualCapture(manualCaptureRef) {
    showManualCapture.value = !showManualCapture.value

    if (showManualCapture.value && manualCaptureRef) {
      nextTick(() => {
        if (manualCaptureRef.$el) {
          manualCaptureRef.$el.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
          })
        }
      })
    }
  }

  /**
   * Toggle file browser and scroll to it
   */
  function toggleFileBrowser(fileBrowserRef) {
    showFileBrowser.value = !showFileBrowser.value

    if (showFileBrowser.value && fileBrowserRef) {
      nextTick(() => {
        if (fileBrowserRef.$el) {
          fileBrowserRef.$el.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
          })
        }
      })
    }
  }

  return {
    // State
    showSettings,
    // showIssuesDashboard removed - migrated to issues-dashboard-cell
    showManualCapture,
    showFileBrowser,

    // Methods
    toggleSettings,
    toggleIssuesDashboard,
    toggleManualCapture,
    toggleFileBrowser,
  }
}
