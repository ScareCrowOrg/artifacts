/**
 * composables/useWorkspaceTheme.ts
 *
 * Reactive theme management synchronized from workspaceStore.
 *
 * Applies theme changes from Cockpit (via postMessage + workspaceStore)
 * to the DOM in a reactive manner.
 */

import { watch, onMounted } from 'vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'
import type { ThemeMode } from '@/stores/workspaceStore'

const log = createLogger('composable:workspace-theme')

const THEME_ATTRIBUTE = 'data-theme'

/**
 * Get system theme preference ('light' or 'dark')
 */
function getSystemTheme(): 'light' | 'dark' {
  if (
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  ) {
    return 'dark'
  }
  return 'light'
}

/**
 * Resolve AUTO theme to actual theme ('light' or 'dark')
 */
function getEffectiveTheme(theme: ThemeMode): 'light' | 'dark' {
  if (theme === 'auto') {
    return getSystemTheme()
  }
  return theme as 'light' | 'dark'
}

/**
 * Apply theme to document
 */
function applyThemeToDOM(theme: ThemeMode) {
  const effective = getEffectiveTheme(theme)
  document.documentElement.setAttribute(THEME_ATTRIBUTE, effective)
  log.debug('[useWorkspaceTheme] Theme applied to DOM', { theme, effective })
}

/**
 * Composable: Reactive theme management from workspaceStore
 *
 * Call this in App.vue or root component to sync theme across all children.
 */
export function useWorkspaceTheme() {
  const store = useWorkspaceStore()

  onMounted(() => {
    log.info('[useWorkspaceTheme] Mounted - setting up reactive theme management')

    // Apply initial theme from store
    applyThemeToDOM(store.theme)

    // Watch for theme changes from postMessage (Cockpit → Viewer)
    const unsubscribe = watch(
      () => store.theme,
      (newTheme) => {
        log.info('[useWorkspaceTheme] Theme changed', { newTheme })
        applyThemeToDOM(newTheme)
      }
    )

    return () => {
      unsubscribe()
    }
  })

  return {
    currentTheme: store.theme,
  }
}

export default useWorkspaceTheme
