/**
 * useAutoLoadCellI18n.ts
 *
 * Discovery-based auto-loading composable for cell translations (Opção C).
 *
 * Implements transparent, plug-and-play i18n for dynamic cells:
 * - Monitors cells array for new cells
 * - Automatically fetches translations from frontend/translations/{locale}.json
 * - Injects with namespacing (cells.{cellTypeName}.{key}) to prevent collisions
 * - Reacts to locale changes from workspaceStore (Cockpit-Vue integration)
 * - Silent background loading: no rendering delays
 * - Graceful failures: cells without translations don't break the system
 *
 * **Cell Developer Constraint:** ZERO i18n code required
 * **Only requirement:** translation files in frontend/translations/{locale}.json
 *
 * Usage in App.vue setup():
 * ```typescript
 * useAutoLoadCellI18n(cells)
 * ```
 */

import { watch, Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'
// Import the i18n instance directly to access .global
// In vue-i18n with legacy: false, useI18n() returns Composer (local instance)
// To access .global (root instance), we need the exported i18n instance
import i18nInstance from '../i18n'
import type { GridCell } from '../types'

const log = createLogger('composable:cell-i18n-auto')

const SCARERUNNER_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SCARERUNNER_URL) ||
  'http://localhost:5050'

/**
 * Auto-discover and load cell translations based on active cells in grid.
 *
 * @param cells - Reactive ref to grid cells array (from useGridLayout)
 */
export function useAutoLoadCellI18n(cells: Ref<GridCell[]>): void {
  const i18nComposer = useI18n() // Local Composer instance (has .locale, .t, etc)
  const store = useWorkspaceStore()

  // Track loaded cells to avoid duplicate requests: "cellTypeName-locale"
  const loadedKeys = new Set<string>()

  // Get the root i18n instance (has .global for mergeLocaleMessage)
  const i18nGlobal = i18nInstance.global

  /**
   * Configure missing handler for graceful fallback during async loading.
   * When a translation key is not yet loaded (async fetch in progress),
   * return the key itself instead of showing [intlify] Not found errors.
   * This enables "silent background loading" - grid renders immediately
   * with raw keys, then translations appear as they load.
   */
  i18nGlobal.missingHandler = (locale: string, key: string) => {
    // Return the key itself for missing translations during async load
    return key
  }

  /**
   * Load translations for a cell type and locale.
   * Merges under namespace: cells.{cellTypeName}
   * Tracks loaded state to avoid HTTP request storms.
   */
  const load = async (cellTypeName: string, locale: string): Promise<void> => {
    const key = `${cellTypeName}-${locale}`

    log.debug('[useAutoLoadCellI18n] load() called', { cellTypeName, locale, key })

    // Skip if already loaded (deduplication)
    if (loadedKeys.has(key)) {
      log.debug('[useAutoLoadCellI18n] Already loaded, skipping', { key })
      return
    }

    try {
      const url = `${SCARERUNNER_URL}/local/canonical/cell_types/${cellTypeName}/frontend/translations/${locale}.json`

      log.debug('[useAutoLoadCellI18n] Loading translations', { cellTypeName, locale })

      const response = await fetch(url)

      if (!response.ok) {
        // 404 or error: cell doesn't have translations for this locale
        log.debug('[useAutoLoadCellI18n] No translations found', {
          cellTypeName,
          locale,
          status: response.status,
        })
        loadedKeys.add(key) // Mark as attempted to avoid retries
        return
      }

      const messages = await response.json()

      if (!messages || Object.keys(messages).length === 0) {
        log.debug('[useAutoLoadCellI18n] Empty translation file', { cellTypeName, locale })
        loadedKeys.add(key)
        return
      }

      // Merge translations directly at root level.
      // File structure: { pngGeneratorCell: { title, description, ... } }
      // View.vue access: t('pngGeneratorCell.title')
      i18nGlobal.mergeLocaleMessage(locale, messages)

      loadedKeys.add(key)

      // Count all keys in loaded messages
      const totalKeys = Object.values(messages).reduce((sum, obj: any) => {
        return sum + (typeof obj === 'object' ? Object.keys(obj).length : 1)
      }, 0)

      log.info('[useAutoLoadCellI18n] Translations merged', {
        cellTypeName,
        locale,
        keyCount: totalKeys,
      })
    } catch (err) {
      // Graceful failure: network error, parse error, etc.
      log.warn('[useAutoLoadCellI18n] Failed to load translations', {
        cellTypeName,
        locale,
        error: err instanceof Error ? err.message : String(err),
      })
      loadedKeys.add(key) // Mark as attempted to avoid retries
    }
  }

  /**
   * WATCHER 1: React to new cells in grid
   * When user adds a cell, load its translations for current locale.
   */
  watch(
    () => cells.value.map(c => c.cellTypeName),
    (names) => {
      try {
        log.debug('[useAutoLoadCellI18n] Cells changed', { count: names.length, names, locale: store.locale })
        log.debug('[useAutoLoadCellI18n] About to forEach', { namesLength: names.length, namesArray: names })
        names.forEach(name => {
          log.debug('[useAutoLoadCellI18n] Watch calling load()', { cellTypeName: name, locale: store.locale })
          load(name, store.locale)
        })
      } catch (err) {
        log.error('[useAutoLoadCellI18n] Watch callback error', { error: err })
      }
    },
    { deep: true },
  )

  /**
   * WATCHER 2: React to locale changes (from Cockpit-Vue via workspaceStore)
   * When user switches language, reload all active cells' translations.
   */
  watch(
    () => store.locale,
    (newLocale) => {
      log.info('[useAutoLoadCellI18n] Locale changed', { newLocale })
      cells.value.forEach(cell => load(cell.cellTypeName, newLocale))
    },
  )

  // Load initial translations for currently visible cells
  cells.value.forEach(cell => load(cell.cellTypeName, store.locale))
}
