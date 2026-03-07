/**
 * composables/useCellI18nRegistry.ts
 *
 * CENTRALIZED i18n management for cells - truly plug-and-play.
 *
 * Zero explicit i18n code in cells. This system:
 * 1. Auto-discovers cells in the grid
 * 2. Auto-loads their translations from frontend/translations/{locale}.json
 * 3. Auto-reloads when locale changes
 * 4. Everything transparent to the cell
 *
 * Cells only need: frontend/translations/{locale}.json files
 */

import { watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:cell-i18n-registry')

const SCARERUNNER_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SCARERUNNER_URL) ||
  'http://localhost:5050'

// Track which cells we've already loaded (to avoid redundant loads)
const loadedCells = new Map<string, Set<string>>() // cellTypeName -> Set of locales loaded

/**
 * Fetch cell translations for a specific locale
 */
async function fetchCellTranslations(cellTypeName: string, locale: string): Promise<Record<string, any>> {
  try {
    const url = `${SCARERUNNER_URL}/local/canonical/cell_types/${cellTypeName}/frontend/translations/${locale}.json`
    const response = await fetch(url)

    if (!response.ok) {
      return {}
    }

    const text = await response.text()

    // Check if response is HTML (error page)
    if (text.trim().startsWith('<')) {
      return {}
    }

    const translations = JSON.parse(text)
    return translations
  } catch (err) {
    log.debug('[CellI18nRegistry] Failed to fetch translations', {
      cellTypeName,
      locale,
      error: err instanceof Error ? err.message : String(err),
    })
    return {}
  }
}

/**
 * Merge translations into global i18n instance
 */
function mergeTranslationsToGlobal(
  cellTypeName: string,
  locale: string,
  translations: Record<string, any>
) {
  if (Object.keys(translations).length === 0) {
    return
  }

  try {
    const i18n = useI18n()
    let i18nGlobal = i18n.global

    // Fallback to window.__i18n
    if (!i18nGlobal) {
      i18nGlobal = (window as any).__i18n?.global
    }

    if (!i18nGlobal) {
      log.warn('[CellI18nRegistry] i18n.global not available', { cellTypeName })
      return
    }

    const currentMessages = i18nGlobal.getLocaleMessage(locale) || {}
    const mergedMessages = { ...currentMessages, ...translations }
    i18nGlobal.setLocaleMessage(locale, mergedMessages)

    log.debug('[CellI18nRegistry] Merged cell translations', {
      cellTypeName,
      locale,
      keyCount: Object.keys(translations).length,
    })
  } catch (err) {
    log.warn('[CellI18nRegistry] Error merging translations', {
      cellTypeName,
      error: err instanceof Error ? err.message : String(err),
    })
  }
}

/**
 * Load translations for a single cell
 */
async function loadCellTranslations(cellTypeName: string, locale: string): Promise<void> {
  // Skip if already loaded
  const cellLoads = loadedCells.get(cellTypeName) || new Set()
  if (cellLoads.has(locale)) {
    log.debug('[CellI18nRegistry] Cell already loaded', { cellTypeName, locale })
    return
  }

  const translations = await fetchCellTranslations(cellTypeName, locale)
  mergeTranslationsToGlobal(cellTypeName, locale, translations)

  // Mark as loaded
  cellLoads.add(locale)
  loadedCells.set(cellTypeName, cellLoads)
}

/**
 * Load translations for multiple cells in parallel
 */
async function loadCellsTranslations(cellTypeNames: string[], locale: string): Promise<void> {
  if (cellTypeNames.length === 0) {
    return
  }

  log.info('[CellI18nRegistry] Loading cell translations', {
    cellCount: cellTypeNames.length,
    locale,
  })

  try {
    await Promise.all(
      cellTypeNames.map((name) => loadCellTranslations(name, locale))
    )
  } catch (err) {
    log.error('[CellI18nRegistry] Error loading cell translations', err)
  }
}

/**
 * PUBLIC: Composable for centralized cell i18n management
 *
 * Usage in App.vue:
 * ```typescript
 * import { useCellI18nRegistry } from '@/composables/useCellI18nRegistry'
 *
 * export default {
 *   setup() {
 *     // Pass the cells ref from useGridLayout
 *     useCellI18nRegistry(cells)
 *   }
 * }
 * ```
 *
 * Flow:
 * 1. App.vue passes reactive cells array to useCellI18nRegistry
 * 2. On mount: extracts cellTypeNames and loads translations for current locale
 * 3. Watch on cells: detects new cells added, loads their translations
 * 4. Watch on locale: reloads ALL cell translations for new locale
 * 5. Everything automatic - cells need zero i18n code
 */
export function useCellI18nRegistry(cellsRef: { value: any[] }) {
  const store = useWorkspaceStore()

  onMounted(() => {
    log.info('[CellI18nRegistry] Mounted - setting up automatic cell i18n management')

    // Load initial cells for current locale
    const cellTypeNames = cellsRef.value.map((cell) => cell.cellTypeName)
    loadCellsTranslations(cellTypeNames, store.locale)

    // Watch for new cells added to grid
    watch(
      () => cellsRef.value.map((cell) => cell.cellTypeName),
      (newNames, oldNames) => {
        const oldSet = new Set(oldNames || [])
        const newCells = newNames.filter((name) => !oldSet.has(name))

        if (newCells.length > 0) {
          log.info('[CellI18nRegistry] New cells detected', {
            newCells,
            locale: store.locale,
          })
          loadCellsTranslations(newCells, store.locale)
        }
      },
      { deep: false }
    )

    // Watch for locale changes - reload ALL cells for new locale
    watch(
      () => store.locale,
      (newLocale) => {
        log.info('[CellI18nRegistry] Locale changed - reloading all cell translations', {
          newLocale,
        })

        // Clear loaded cache for this locale to force reload
        loadedCells.forEach((locales) => {
          locales.delete(newLocale)
        })

        // Reload all cells for new locale
        const allCellTypeNames = cellsRef.value.map((cell) => cell.cellTypeName)
        loadCellsTranslations(allCellTypeNames, newLocale)
      }
    )
  })
}

export default useCellI18nRegistry
