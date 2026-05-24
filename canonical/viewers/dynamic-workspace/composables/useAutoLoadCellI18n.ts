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
import i18nInstance from '@/i18n'
import type { GridCell } from '../types'

const log = createLogger('composable:cell-i18n-auto')

// Note: SCARERUNNER_URL is no longer used for i18n files.
// Translations are loaded via fetch() with paths resolved through the browser's import map.
// This avoids /local endpoint dependency and works in both dev and production.

/**
 * Normalize locale codes to match translation file naming.
 * Cockpit-Vue may send full locale codes (e.g., en-US, pt-BR)
 * but translation files use simplified codes (en, pt-BR, etc).
 */
function normalizeLocale(locale: string): string {
  // Map full locale codes to translation file names
  const localeMap: Record<string, string> = {
    'en-US': 'en',
    'en-GB': 'en',
    'en-AU': 'en',
    'en': 'en',
    'pt-BR': 'pt-BR',
    'pt': 'pt-BR',
  }
  return localeMap[locale] || locale
}

/**
 * Auto-discover and load cell translations based on active cells in grid.
 *
 * @param cells - Reactive ref to grid cells array (from useGridLayout)
 */
export function useAutoLoadCellI18n(cells: Ref<GridCell[]>): void {
  const i18nComposer = useI18n() // Local Composer instance (has .locale, .t, etc)
  const store = useWorkspaceStore()

  // Sync i18n locale with workspace store locale
  // This ensures templates use correct locale when translations are merged
  const syncLocale = (locale: string) => {
    const normalizedLocale = normalizeLocale(locale)
    if (i18nComposer.locale.value !== normalizedLocale) {
      log.debug('[useAutoLoadCellI18n] Syncing i18n locale', {
        from: i18nComposer.locale.value,
        to: normalizedLocale,
      })
      i18nComposer.locale.value = normalizedLocale
    }
  }

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
   *
   * Uses fetch() to load JSON translation files from artifacts.
   * Falls back gracefully if translations don't exist (404 is normal for cells without i18n).
   */
  const load = async (cellTypeName: string, locale: string): Promise<void> => {
    // Normalize locale to match translation file naming convention
    const normalizedLocale = normalizeLocale(locale)
    const key = `${cellTypeName}-${normalizedLocale}`

    log.debug('[useAutoLoadCellI18n] load() called', { cellTypeName, locale, normalizedLocale, key })

    // Skip if already loaded (deduplication)
    if (loadedKeys.has(key)) {
      log.debug('[useAutoLoadCellI18n] Already loaded, skipping', { key })
      return
    }

    try {
      // Path: #artifacts/canonical/cell_types/{cellTypeName}/frontend/translations/{locale}.json
      // Resolved via import map in index.html
      const translationPath = `#artifacts/canonical/cell_types/${cellTypeName}/frontend/translations/${normalizedLocale}.json`

      log.debug('[useAutoLoadCellI18n] Loading translations', {
        cellTypeName,
        locale,
        normalizedLocale,
        translationPath,
      })

      // Use fetch() to load translation file — more reliable for JSON
      // import maps are still used for #artifacts/ path resolution via index.html
      let messages: Record<string, any> | null = null
      try {
        const response = await fetch(translationPath)
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        messages = await response.json()
      } catch (fetchError) {
        // 404 or other error: cell doesn't have translations for this locale
        // This is normal and expected - not all cells have translations
        log.debug('[useAutoLoadCellI18n] No translations found', {
          cellTypeName,
          normalizedLocale,
          error: fetchError instanceof Error ? fetchError.message : String(fetchError),
        })
        loadedKeys.add(key) // Mark as attempted to avoid retries
        return
      }

      if (!messages || Object.keys(messages).length === 0) {
        log.debug('[useAutoLoadCellI18n] Empty translation file', { cellTypeName, normalizedLocale })
        loadedKeys.add(key)
        return
      }

      // Merge translations directly at root level.
      // File structure: { pngGeneratorCell: { title, description, ... } }
      // View.vue access: t('pngGeneratorCell.title')
      i18nGlobal.mergeLocaleMessage(normalizedLocale, messages)

      loadedKeys.add(key)

      // Count all keys in loaded messages
      const totalKeys = Object.values(messages).reduce((sum, obj: any) => {
        return sum + (typeof obj === 'object' ? Object.keys(obj).length : 1)
      }, 0)

      log.info('[useAutoLoadCellI18n] Translations merged', {
        cellTypeName,
        normalizedLocale,
        keyCount: totalKeys,
      })
    } catch (err) {
      // Graceful failure: import error, parse error, etc.
      log.warn('[useAutoLoadCellI18n] Failed to load translations', {
        cellTypeName,
        normalizedLocale,
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
        const rawLocale = store.locale
        const currentLocale = rawLocale || 'en' // Default to English if empty
        log.debug('[useAutoLoadCellI18n] Cells changed', {
          count: names.length,
          names,
          rawLocale: `"${rawLocale}"`,
          currentLocale,
          isEmptyRaw: !rawLocale,
        })
        // Ensure i18n locale matches store locale
        syncLocale(currentLocale)
        // Then load translations
        names.forEach(name => {
          log.debug('[useAutoLoadCellI18n] Watch calling load()', {
            cellTypeName: name,
            rawLocale: `"${rawLocale}"`,
            currentLocale,
          })
          load(name, currentLocale)
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
      const currentLocale = newLocale || 'en' // Default to English if empty
      log.info('[useAutoLoadCellI18n] Locale changed', {
        newLocale: `"${newLocale}"`,
        currentLocale,
        isEmptyNew: !newLocale,
        cellCount: cells.value.length,
      })
      // Sync i18n locale immediately so templates use correct locale
      syncLocale(currentLocale)
      // Then load translations for new locale
      cells.value.forEach(cell => load(cell.cellTypeName, currentLocale))
    },
  )

  // Load initial translations for currently visible cells at setup time
  const initialRawLocale = store.locale
  const initialLocale = initialRawLocale || 'en' // Default to English if not set
  log.debug('[useAutoLoadCellI18n] SETUP - Initial load', {
    initialRawLocale: `"${initialRawLocale}"`,
    initialLocale,
    cellCount: cells.value.length,
    isEmptyRaw: !initialRawLocale,
  })
  // Ensure i18n locale matches from the start
  syncLocale(initialLocale)
  cells.value.forEach(cell => load(cell.cellTypeName, initialLocale))
}
