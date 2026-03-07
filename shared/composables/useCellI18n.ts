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
 * ⚠️ IMPORTANT: MUST be awaited to ensure translations load before component renders!
 *
 * ```typescript
 * await useCellI18n('png-generator-cell')
 * ```
 *
 * Returns a Promise that blocks until translations are loaded or an error occurs.
 *
 * @param cellTypeName - Semantic cell type name (e.g. "png-generator-cell")
 * @returns Promise<void> - resolves when translations are loaded and merged
 */
export async function useCellI18n(cellTypeName: string): Promise<void> {
  const i18n = useI18n()

  console.log('[useCellI18n] ENTRY - Loading translations for cell', {
    cellTypeName,
    currentLocale: i18n.locale.value,
    timestamp: new Date().toISOString(),
  })

  try {
    // Load translations for current locale - THIS BLOCKS until complete
    const translations = await loadCellTranslations(cellTypeName, i18n.locale.value)

    if (translations && Object.keys(translations).length > 0) {
      console.log('[useCellI18n] Loaded translations successfully', {
        cellTypeName,
        locale: i18n.locale.value,
        keyCount: Object.keys(translations).length,
        keys: Object.keys(translations),
      })

      // ⚡ ATOMIC MERGE: All at once, not key-by-key
      // BUT FIRST: Check if i18n.global is available (might be undefined in isolated contexts)
      if (!i18n.global) {
        console.error('[useCellI18n] ⚠️ i18n.global is undefined - cannot merge translations', {
          cellTypeName,
          locale: i18n.locale.value,
          hasI18n: !!i18n,
          i18nKeys: i18n ? Object.keys(i18n) : [],
        })
        throw new Error('i18n.global is undefined - i18n not properly initialized in component context')
      }

      const currentMessages = i18n.global.getLocaleMessage(i18n.locale.value) || {}
      const mergedMessages = {
        ...currentMessages,
        ...translations,
      }

      console.log('[useCellI18n] Merging into i18n', {
        cellTypeName,
        locale: i18n.locale.value,
        beforeMergeKeys: Object.keys(currentMessages).length,
        newKeys: Object.keys(translations).length,
        afterMergeKeys: Object.keys(mergedMessages).length,
      })

      i18n.global.setLocaleMessage(i18n.locale.value, mergedMessages)

      console.log('[useCellI18n] ✅ SUCCESS - Translations fully loaded and merged', {
        cellTypeName,
        locale: i18n.locale.value,
        timestamp: new Date().toISOString(),
      })
    } else {
      console.warn('[useCellI18n] ⚠️ NO TRANSLATIONS FOUND', {
        cellTypeName,
        locale: i18n.locale.value,
        isEmpty: !translations || Object.keys(translations).length === 0,
      })
    }
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err)

    console.error('[useCellI18n] ❌ FAILED to load translations', {
      cellTypeName,
      locale: i18n.locale.value,
      error: errorMsg,
      stack: err instanceof Error ? err.stack : undefined,
      timestamp: new Date().toISOString(),
      debugInfo: {
        hasI18nGlobal: !!i18n?.global,
        i18nContextReady: !errorMsg.includes('i18n.global'),
        errorType: errorMsg.includes('Cannot read') ? 'context_issue' : 'other',
      },
    })

    log.error('[useCellI18n] Failed to load cell translations', {
      cellTypeName,
      locale: i18n.locale.value,
      error: errorMsg,
      hint: errorMsg.includes('i18n.global') ? 'i18n context may not be available - check if component has access to i18n plugin' : 'unknown error',
    })
    throw err
  }
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
