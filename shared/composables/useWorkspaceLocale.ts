/**
 * composables/useWorkspaceLocale.ts
 *
 * Reactive locale management synchronized from workspaceStore.
 *
 * ⚠️ IMPORTANT: This composable handles i18n locale switching.
 * Cells using useCellI18n MUST be aware that when locale changes:
 * 1. useWorkspaceLocale updates i18n.locale.value
 * 2. useCellI18n automatically detects the change and reloads translations
 *
 * For this to work properly:
 * - Call useWorkspaceLocale() in App.vue or root component
 * - Each cell MUST use useCellI18n() with reactive watcher for locale changes
 */

import { watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:workspace-locale')

/**
 * Composable: Reactive locale management from workspaceStore
 *
 * Usage in App.vue:
 * ```typescript
 * import { useWorkspaceLocale } from '@/composables/useWorkspaceLocale'
 *
 * export default {
 *   setup() {
 *     useWorkspaceLocale()  // Just call it, no return needed
 *     // ... rest of setup
 *   }
 * }
 * ```
 *
 * Flow:
 * 1. useWorkspaceLocale() mounts and applies initial locale from store
 * 2. Watch subscription monitors store.locale
 * 3. When Cockpit sends SWITCH_LOCALE or SYNC_CONFIG via postMessage
 * 4. workspaceStore.locale updates
 * 5. Watch fires and updates i18n.locale.value
 * 6. Components and cells reactively re-render
 * 7. useCellI18n detects locale change via its own watcher and reloads cell translations
 */
export function useWorkspaceLocale() {
  const store = useWorkspaceStore()
  const i18n = useI18n()

  /**
   * Update i18n locale (this is reactive and triggers component updates)
   */
  function setLocale(locale: string) {
    if (!i18n.locale) {
      log.warn('[useWorkspaceLocale] i18n.locale not available', { locale })
      return
    }

    const oldLocale = i18n.locale.value
    i18n.locale.value = locale

    log.info('[useWorkspaceLocale] Locale switched in i18n', {
      from: oldLocale,
      to: locale,
    })
  }

  onMounted(() => {
    log.info('[useWorkspaceLocale] Mounted - setting up reactive locale management')

    // Apply initial locale from store
    setLocale(store.locale)

    // Watch for locale changes from workspaceStore
    // Fires when:
    // - SYNC_CONFIG received (initial sync after handshake)
    // - SWITCH_LOCALE received (user changed language in Cockpit)
    const unsubscribe = watch(
      () => store.locale,
      (newLocale) => {
        log.info('[useWorkspaceLocale] Locale changed in store', {
          newLocale,
          triggersI18nUpdate: true,
          cellsWillReload: true,
        })
        setLocale(newLocale)
      }
    )

    return () => {
      unsubscribe()
    }
  })

  return {
    currentLocale: store.locale,
  }
}

export default useWorkspaceLocale
