/**
 * useAutoLoadCellI18n.ts
 *
 * Discovery-based auto-loading composable for cell translations.
 *
 * Implements Opção C (Discovery-Based Auto-Loading):
 * - Monitors cells array for new cells
 * - Automatically fetches translations for each cell type
 * - Injects with namespacing (cells.{cellTypeName}.{key})
 * - Reacts to locale changes from workspaceStore
 * - Silent failures: missing translation files don't break the system
 *
 * **Constraint:** Cell developers write ZERO i18n code.
 * **Only requirement:** translation files in frontend/translations/{locale}.json
 *
 * Usage in App.vue:
 * ```typescript
 * useAutoLoadCellI18n(cells)
 * ```
 */

import { watch, Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'
import type { GridCell } from '../types'

const log = createLogger('composable:cell-i18n-auto')

const SCARERUNNER_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SCARERUNNER_URL) ||
  'http://localhost:5050'

/**
 * Tracks loaded cells to avoid duplicate requests.
 * Key format: "cellTypeName-locale"
 */
const loadedCells = new Set<string>()

/**
 * Auto-discover and load cell translations based on active cells in grid.
 *
 * @param cells - Reactive ref to grid cells array (from useGridLayout)
 */
export function useAutoLoadCellI18n(cells: Ref<GridCell[]>): void {
  const i18n = useI18n()
  const store = useWorkspaceStore()

  /**
   * Load a single cell's translations for a given locale.
   * Translations are injected under namespace: cells.{cellTypeName}
   */
  async function loadCellTranslations(cellTypeName: string, locale: string): Promise<void> {
    const cacheKey = `${cellTypeName}-${locale}`

    // Skip if already loaded
    if (loadedCells.has(cacheKey)) {
      log.debug('[useAutoLoadCellI18n] Already loaded', { cellTypeName, locale })
      return
    }

    try {
      const url = `${SCARERUNNER_URL}/local/canonical/cell_types/${cellTypeName}/frontend/translations/${locale}.json`

      log.debug('[useAutoLoadCellI18n] Fetching', { cellTypeName, locale, url })

      const response = await fetch(url)

      if (!response.ok) {
        // 404 or other error: cell doesn't have translations for this locale
        log.debug('[useAutoLoadCellI18n] No translations found', {
          cellTypeName,
          locale,
          status: response.status,
        })
        loadedCells.add(cacheKey) // Mark as attempted to avoid retry storm
        return
      }

      const translations = await response.json()

      if (!translations || Object.keys(translations).length === 0) {
        log.debug('[useAutoLoadCellI18n] Empty translations', { cellTypeName, locale })
        loadedCells.add(cacheKey)
        return
      }

      // Inject under namespace to prevent key collisions
      // Result: t('cells.png-generator-cell.title')
      const namespaced = {
        cells: {
          [cellTypeName]: translations,
        },
      }

      i18n.global.mergeLocaleMessage(locale, namespaced)
      loadedCells.add(cacheKey)

      log.info('[useAutoLoadCellI18n] Translations loaded', {
        cellTypeName,
        locale,
        keyCount: Object.keys(translations).length,
      })
    } catch (err) {
      // Network error, parse error, etc. — silent failure
      log.warn('[useAutoLoadCellI18n] Failed to load translations', {
        cellTypeName,
        locale,
        error: err instanceof Error ? err.message : String(err),
      })
      loadedCells.add(cacheKey) // Mark as attempted
    }
  }

  /**
   * Extract unique cell type names from grid.
   */
  function getCellTypeNames(): string[] {
    return [...new Set(cells.value.map(cell => cell.cellTypeName))]
  }

  /**
   * WATCHER 1: React to new cells in grid
   * When user adds a cell, load its translations for current locale.
   */
  watch(
    () => getCellTypeNames(),
    (cellTypeNames) => {
      log.debug('[useAutoLoadCellI18n] Cells changed', { cellTypeNames })
      cellTypeNames.forEach(name => {
        loadCellTranslations(name, store.locale)
      })
    },
    { deep: true }, // Watch array mutations (add/remove cells)
  )

  /**
   * WATCHER 2: React to locale changes (from Cockpit-Vue via workspaceStore)
   * When user switches language, reload all active cells' translations.
   */
  watch(
    () => store.locale,
    (newLocale) => {
      log.info('[useAutoLoadCellI18n] Locale changed', { newLocale })
      const cellTypeNames = getCellTypeNames()
      cellTypeNames.forEach(name => {
        loadCellTranslations(name, newLocale)
      })
    },
  )

  // Load initial translations for currently visible cells
  const initialCellNames = getCellTypeNames()
  initialCellNames.forEach(name => {
    loadCellTranslations(name, store.locale)
  })
}
