/**
 * useLocaleSync.ts
 *
 * Synchronizes viewer locale from cockpit-vue (via workspaceStore) with vue-i18n.
 *
 * Cockpit sends locale codes like 'en-US' / 'pt-BR' but vue-i18n in viewers
 * expects abbreviated codes like 'en' / 'pt-BR'. Uses normalizeLocale() to bridge.
 *
 * Any viewer can opt into locale synchronization by calling useLocaleSync()
 * after useBaseViewer() in setup().
 */

import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'
import { normalizeLocale } from '@/utils/i18nUtils'

const log = createLogger('composable:locale-sync')

export function useLocaleSync(): void {
  const composer = useI18n()
  const store = useWorkspaceStore()

  const syncLocale = (locale: string) => {
    const normalized = normalizeLocale(locale)
    if (composer.locale.value !== normalized) {
      composer.locale.value = normalized
      log.debug('[useLocaleSync] Locale synced', { from: composer.locale.value, to: normalized })
    }
  }

  // Apply initial locale
  const initialLocale = store.locale || navigator.language?.split('-')[0] || 'en'
  syncLocale(initialLocale)

  // Watch for changes from Cockpit-Vue (SWITCH_LOCALE / SYNC_CONFIG)
  watch(() => store.locale, (newLocale) => {
    syncLocale(newLocale || 'en')
  })
}
