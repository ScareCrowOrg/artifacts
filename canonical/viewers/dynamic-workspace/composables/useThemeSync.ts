/**
 * useThemeSync.ts
 *
 * Synchronizes workspace theme (from Cockpit-Vue via workspaceStore) with DOM.
 *
 * Applies the 'dark' class to document.documentElement when theme is 'dark',
 * enabling Tailwind CSS dark mode classes (dark:bg-gray-950, etc).
 *
 * Also applies [data-theme='dark'] attribute for CSS variable customization.
 */

import { watch } from 'vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:theme-sync')

/**
 * Apply theme from workspace store to DOM.
 * Watches store.theme changes and updates document.documentElement classes.
 */
export function useThemeSync(): void {
  const store = useWorkspaceStore()

  /**
   * Apply theme to DOM
   * - 'dark' theme: adds 'dark' class and [data-theme='dark'] attribute
   * - 'light' theme: removes both
   * - 'auto' theme: let system preference decide (remove class, browser handles via prefers-color-scheme)
   */
  const applyTheme = (theme: string) => {
    const htmlElement = document.documentElement

    log.debug('[useThemeSync] Applying theme', { theme })

    if (theme === 'dark') {
      htmlElement.classList.add('dark')
      htmlElement.setAttribute('data-theme', 'dark')
      log.info('[useThemeSync] Dark mode enabled', {
        hasDarkClass: htmlElement.classList.contains('dark'),
        dataTheme: htmlElement.getAttribute('data-theme'),
      })
    } else if (theme === 'light') {
      htmlElement.classList.remove('dark')
      htmlElement.removeAttribute('data-theme')
      log.info('[useThemeSync] Light mode enabled', {
        hasDarkClass: htmlElement.classList.contains('dark'),
        dataTheme: htmlElement.getAttribute('data-theme'),
      })
    } else if (theme === 'auto') {
      // Let browser handle via prefers-color-scheme
      htmlElement.classList.remove('dark')
      htmlElement.removeAttribute('data-theme')
      log.info('[useThemeSync] Auto mode enabled (system preference)', {
        hasDarkClass: htmlElement.classList.contains('dark'),
      })
    }
  }

  // Apply initial theme on setup
  const initialTheme = store.theme || 'auto'
  log.debug('[useThemeSync] SETUP - Initial theme', { theme: initialTheme })
  applyTheme(initialTheme)

  // Watch for theme changes from Cockpit-Vue
  watch(
    () => store.theme,
    (newTheme) => {
      const theme = newTheme || 'auto'
      log.info('[useThemeSync] Theme changed from Cockpit-Vue', {
        newTheme: theme,
        timestamp: new Date().toISOString(),
      })
      applyTheme(theme)
    },
  )
}
