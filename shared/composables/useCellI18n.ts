/**
 * composables/useCellI18n.ts
 *
 * Automatic translation loader for cell View components.
 *
 * Each cell can have its own translations in: frontend/translations/{locale}.json
 * This composable loads them and merges into the app's i18n instance.
 *
 * Usage in cell View.vue:
 * ```
 * import { useCellI18n } from '@/composables/useCellI18n'
 * import { onMounted } from 'vue'
 *
 * onMounted(() => {
 *   useCellI18n('png-generator-cell')
 * })
 * ```
 */

import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:cell-i18n')

const SCARERUNNER_URL =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_SCARERUNNER_URL) ||
  'http://localhost:5050'

/**
 * Load cell-specific translations and merge into global i18n instance.
 *
 * @param cellTypeName - Semantic cell type name (e.g. "png-generator-cell")
 */
export function useCellI18n(cellTypeName: string): void {
  const i18n = useI18n()

  console.log('[useCellI18n] ENTRY - Loading translations for cell', {
    cellTypeName,
    currentLocale: i18n.locale.value,
  })

  // Try to load translations for current locale
  loadCellTranslations(cellTypeName, i18n.locale.value)
    .then((translations) => {
      if (translations && Object.keys(translations).length > 0) {
        console.log('[useCellI18n] Loaded translations for locale', {
          cellTypeName,
          locale: i18n.locale.value,
          keys: Object.keys(translations),
        })

        // Merge cell translations into global i18n
        Object.entries(translations).forEach(([key, value]) => {
          console.log(`[useCellI18n] Merging key: ${key}`)
          i18n.global.setLocaleMessage(i18n.locale.value, {
            ...i18n.global.getLocaleMessage(i18n.locale.value),
            [key]: value,
          })
        })

        console.log('[useCellI18n] SUCCESS - Translations merged into i18n', {
          cellTypeName,
          locale: i18n.locale.value,
        })
      }
    })
    .catch((err) => {
      log.warn('[useCellI18n] Failed to load cell translations', {
        cellTypeName,
        locale: i18n.locale.value,
        error: err instanceof Error ? err.message : String(err),
      })
      console.log('[useCellI18n] WARNING - Could not load translations', {
        cellTypeName,
        locale: i18n.locale.value,
        error: err instanceof Error ? err.message : String(err),
      })
    })
}

/**
 * Fetch and parse cell translation file.
 *
 * @param cellTypeName - Cell type (e.g. "png-generator-cell")
 * @param locale - Locale code (e.g. "pt-BR", "en")
 * @returns Promise<translations> or empty object if not found
 */
async function loadCellTranslations(cellTypeName: string, locale: string): Promise<Record<string, any>> {
  console.log('[loadCellTranslations] BEFORE fetch', {
    cellTypeName,
    locale,
  })

  try {
    // Try the requested locale first
    const url = `${SCARERUNNER_URL}/local/canonical/cell_types/${cellTypeName}/frontend/translations/${locale}.json`
    console.log('[loadCellTranslations] Fetching from URL', { url })

    const response = await fetch(url)

    console.log('[loadCellTranslations] AFTER fetch', {
      cellTypeName,
      locale,
      status: response.status,
      ok: response.ok,
    })

    if (!response.ok) {
      console.log('[loadCellTranslations] Fetch failed', {
        cellTypeName,
        locale,
        status: response.status,
      })
      return {}
    }

    const text = await response.text()

    // Check if response is HTML (error page)
    if (text.trim().startsWith('<')) {
      console.log('[loadCellTranslations] Received HTML instead of JSON', {
        cellTypeName,
        locale,
      })
      return {}
    }

    const translations = JSON.parse(text)
    console.log('[loadCellTranslations] PARSED translations', {
      cellTypeName,
      locale,
      keys: Object.keys(translations),
    })

    return translations
  } catch (err) {
    console.log('[loadCellTranslations] ERROR during fetch/parse', {
      cellTypeName,
      locale,
      error: err instanceof Error ? err.message : String(err),
    })
    return {}
  }
}
