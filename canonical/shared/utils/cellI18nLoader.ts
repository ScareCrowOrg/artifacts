/**
 * cellI18nLoader.ts
 *
 * Standalone utility for loading cell i18n translations outside of the grid.
 *
 * Extracted from useAutoLoadCellI18n — same import + merge pattern,
 * but callable from anywhere, including View.vue of parent cells
 * that compose sub-cells (e.g. inbox-cell -> messages-cell, requests-cell).
 *
 * Usage:
 *   import { loadCellsI18n } from '#canonical/shared/utils/cellI18nLoader'
 *   onMounted(() => { loadCellsI18n(['messages-cell', 'requests-cell']) })
 */

import i18nInstance from '@/i18n'
import { createLogger } from '@/utils/logger'

const log = createLogger('util:cell-i18n-loader')

/**
 * Normalize locale codes to match translation file naming.
 */
function normalizeLocale(locale: string): string {
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

// Track loaded cells to avoid duplicate imports: "cellTypeName-locale"
const loadedKeys = new Set<string>()

/**
 * Load and merge i18n translations for a single cell type.
 *
 * Uses Vite dynamic import with #canonical alias to load translation JSON.
 * Vite resolves #canonical/ to /app/artifacts/canonical/ via its alias config.
 * Works in ALL environments (Docker, staging, cloud) because:
 * - File is inside artifacts/ → served by Vite compilation service
 * - Vite compiles the import() and resolves the #canonical alias at serve time
 * - Translation JSON files are transformed to ES modules by Vite automatically
 *
 * Deduplication: safe to call multiple times for the same (cellTypeName, locale).
 * Graceful failure: missing translation file = no-op, returns false.
 *
 * @param cellTypeName - e.g. 'messages-cell', 'requests-cell'
 * @param locale - defaults to current i18n locale
 * @returns true if translations were loaded and merged
 */
export async function loadCellI18n(
  cellTypeName: string,
  locale?: string,
): Promise<boolean> {
  const currentLocale = locale || i18nInstance.global.locale.value
  const normalizedLocale = normalizeLocale(currentLocale)
  const key = `${cellTypeName}-${normalizedLocale}`

  if (loadedKeys.has(key)) {
    log.debug('[loadCellI18n] Already loaded, skipping', { key })
    return true
  }

  try {
    // Dynamic import via Vite's #canonical alias.
    // Vite resolves #canonical/ to /app/artifacts/canonical/ and serves the file.
    // JSON imports are automatically transformed to ES modules by Vite.
    const translationSpecifier =
      `#canonical/cell_types/${cellTypeName}/frontend/translations/${normalizedLocale}.json` as string

    log.debug('[loadCellI18n] Loading translations', {
      cellTypeName,
      normalizedLocale,
      translationSpecifier,
    })

    let messages: Record<string, any> | null = null
    try {
      const module = await import(translationSpecifier)
      messages = module.default || module
    } catch (importError) {
      log.debug('[loadCellI18n] No translations found', {
        cellTypeName,
        normalizedLocale,
        error: importError instanceof Error ? importError.message : String(importError),
      })
      loadedKeys.add(key)
      return false
    }

    if (!messages || Object.keys(messages).length === 0) {
      log.debug('[loadCellI18n] Empty translation file', { cellTypeName, normalizedLocale })
      loadedKeys.add(key)
      return false
    }

    // Merge at root level so $t('messagesCell.reply') works directly
    // IMPORTANT: merge into both normalized AND current locale
    // When locale='pt', normalizeLocale maps it to 'pt-BR' for file lookup.
    // The translation file pt-BR.json is loaded, but vue-i18n's active locale
    // might still be 'pt'. Merging only into 'pt-BR' means $t() won't find
    // the keys because it searches the active 'pt' locale, not 'pt-BR'.
    i18nInstance.global.mergeLocaleMessage(normalizedLocale, messages)
    if (normalizedLocale !== currentLocale) {
      i18nInstance.global.mergeLocaleMessage(currentLocale, messages)
    }

    loadedKeys.add(key)

    const totalKeys = Object.values(messages).reduce((sum: number, obj: any) => {
      return sum + (typeof obj === 'object' ? Object.keys(obj).length : 1)
    }, 0)

    log.info('[loadCellI18n] Translations merged', {
      cellTypeName,
      normalizedLocale,
      keyCount: totalKeys,
    })

    return true
  } catch (err) {
    log.warn('[loadCellI18n] Failed to load translations', {
      cellTypeName,
      normalizedLocale,
      error: err instanceof Error ? err.message : String(err),
    })
    loadedKeys.add(key)
    return false
  }
}

/**
 * Pre-load translations for multiple cell types at once.
 * All loads happen in parallel.
 *
 * @param cellTypeNames - e.g. ['messages-cell', 'requests-cell']
 * @param locale - defaults to current i18n locale
 * @returns map of cellTypeName → success boolean
 */
export async function loadCellsI18n(
  cellTypeNames: string[],
  locale?: string,
): Promise<Record<string, boolean>> {
  const results = await Promise.allSettled(
    cellTypeNames.map((name) => loadCellI18n(name, locale)),
  )

  const resultMap: Record<string, boolean> = {}
  cellTypeNames.forEach((name, i) => {
    resultMap[name] = results[i].status === 'fulfilled' && results[i].value
  })

  return resultMap
}
