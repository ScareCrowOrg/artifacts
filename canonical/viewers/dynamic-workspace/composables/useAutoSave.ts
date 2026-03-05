/**
 * composables/useAutoSave.ts
 *
 * Background auto-save for DynamicWorkspace v2 — Phase 3.
 *
 * Strategy:
 * - Debounced save: waits AUTOSAVE_DEBOUNCE_MS of "quiet time" after a grid
 *   change before persisting. Prevents API spam when the user is dragging cells.
 * - Fallback interval: also saves every AUTOSAVE_INTERVAL_MS regardless of
 *   change events (safety net in case watchers miss updates).
 * - Non-blocking: failures are logged but never propagate to the UI.
 * - Tracks a single "auto-save" book ID per session (avoids cluttering the
 *   layout list with duplicate entries).
 */

import { ref, watch, readonly } from 'vue'
import { useGridLayout } from './useGridLayout'
import { usePersistenceManager } from './usePersistenceManager'
import { createLogger } from '@/utils/logger'

const log = createLogger('workspace:auto-save')

// ── Timing constants ──────────────────────────────────────────────────────────

const AUTOSAVE_DEBOUNCE_MS = 3_000   // 3 s of quiet after last change
const AUTOSAVE_INTERVAL_MS = 30_000  // Fallback every 30 s

// ── Composable ────────────────────────────────────────────────────────────────

export function useAutoSave() {
  const { cells } = useGridLayout()
  const { autoSaveWorkspaceState } = usePersistenceManager()

  // ── State ──────────────────────────────────────────────────────────────────

  /** ID of the current session's auto-save layout book */
  const autoSaveBookId = ref<string | null>(null)

  /** Whether auto-save is enabled */
  const isAutoSaveEnabled = ref(false)

  /** Whether the current grid state differs from the last saved state */
  const hasUnsavedChanges = ref(false)

  /** Snapshot of the cell list at the time of the last successful save */
  let lastSavedSnapshot: string = ''

  /** Timer refs for debounce and interval */
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let intervalTimer: ReturnType<typeof setInterval> | null = null
  /** Stop function for the Vue watcher (returned by watch()) */
  let stopWatcher: (() => void) | null = null

  // ── Helpers ────────────────────────────────────────────────────────────────

  /**
   * Cheap JSON snapshot of cell ids + positions + states (no Vue components).
   *
   * IMPORTANT: This watcher depends on position being reassigned (not mutated
   * in-place). If a cell's position is mutated directly (e.g. `cell.position.x = 10`),
   * the watch will NOT trigger and auto-save will miss the change.
   *
   * Current design: `useGridLayout.syncLayoutPositions` reassigns position objects
   * (`cell.position = updatedPositions[cell.cellId]`), so this is safe.
   *
   * Future: If position changes to in-place mutations elsewhere, switch to a
   * deep watch or compute a diff-based snapshot that reads individual coordinates.
   */
  function buildSnapshot(): string {
    return JSON.stringify(
      cells.value.map(c => ({
        id: c.cellId,
        type: c.cellTypeName,
        pos: c.position ?? { x: 0, y: 0, w: 6, h: 8 },
        min: c.isMinimized ?? false,
        max: c.isMaximized ?? false,
      })),
    )
  }

  async function performAutoSave(): Promise<void> {
    if (cells.value.length === 0) {
      log.debug('[AutoSave] No cells to save, skipping')
      return
    }

    try {
      const newId = await autoSaveWorkspaceState(autoSaveBookId.value)
      autoSaveBookId.value = newId
      lastSavedSnapshot = buildSnapshot()
      hasUnsavedChanges.value = false
      log.info('[AutoSave] Workspace state saved', {
        autoSaveBookId: newId,
        cellCount: cells.value.length,
        timestamp: new Date().toISOString(),
      })
    } catch (err: any) {
      // Auto-save failures must not block the user
      log.warn('[AutoSave] Failed (will retry)', { error: err.message })
    }
  }

  function triggerDebounced(): void {
    // Mark as unsaved immediately so the UI can show the indicator
    hasUnsavedChanges.value = true

    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
    }

    debounceTimer = setTimeout(() => {
      debounceTimer = null
      performAutoSave()
    }, AUTOSAVE_DEBOUNCE_MS)
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  /**
   * Enable auto-save: watch for grid changes and run periodic fallback saves.
   * Call once on component mount.
   */
  function enableAutoSave(): void {
    if (isAutoSaveEnabled.value) return

    isAutoSaveEnabled.value = true
    lastSavedSnapshot = buildSnapshot()

    // Debounced watch: fires when the cells array length changes or any cell's
    // position/state changes. Using a getter that serializes key fields keeps
    // the watch lean without deep-watching Vue components inside GridCell.
    stopWatcher = watch(
      () => buildSnapshot(),
      (next, prev) => {
        if (next !== prev) {
          triggerDebounced()
        }
      },
    )

    // Fallback interval (safety net)
    intervalTimer = setInterval(() => {
      if (hasUnsavedChanges.value) {
        log.debug('[AutoSave] Fallback interval: running save')
        performAutoSave()
      }
    }, AUTOSAVE_INTERVAL_MS)

    log.info('[AutoSave] Enabled', {
      debounceMs: AUTOSAVE_DEBOUNCE_MS,
      intervalMs: AUTOSAVE_INTERVAL_MS,
    })
  }

  /**
   * Disable auto-save and clear all timers.
   */
  function disableAutoSave(): void {
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (intervalTimer !== null) {
      clearInterval(intervalTimer)
      intervalTimer = null
    }
    if (stopWatcher !== null) {
      stopWatcher()
      stopWatcher = null
    }
    isAutoSaveEnabled.value = false
    log.info('[AutoSave] Disabled')
  }

  /**
   * Immediately persist the current workspace state (manual trigger).
   */
  async function saveNow(): Promise<void> {
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    await performAutoSave()
  }

  return {
    enableAutoSave,
    disableAutoSave,
    saveNow,
    hasUnsavedChanges: readonly(hasUnsavedChanges),
    isAutoSaveEnabled: readonly(isAutoSaveEnabled),
    autoSaveBookId: readonly(autoSaveBookId),
  }
}
