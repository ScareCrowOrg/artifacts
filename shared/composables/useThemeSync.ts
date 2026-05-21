/**
 * useThemeSync.ts
 *
 * Synchronizes workspace theme (from Cockpit-Vue via workspaceStore) with DOM.
 * Moved from dynamic-workspace/composables/useThemeSync.ts to shared so any
 * viewer can opt into theme synchronization.
 *
 * Improvements over dynamic-workspace original:
 * 1. Resolves 'auto' via prefers-color-scheme (not just removing class)
 * 2. Adds matchMedia listener to react to OS-level theme changes in real time
 *
 * Applies the 'dark' class to document.documentElement when theme resolves to 'dark',
 * enabling Tailwind CSS dark mode classes (dark:bg-gray-950, etc).
 * Also applies [data-theme='dark'] attribute for CSS variable customization.
 */

import { watch, onUnmounted } from 'vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { createLogger } from '@/utils/logger'

const log = createLogger('composable:theme-sync')

function resolveTheme(theme: string): string {
  if (theme === 'auto') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return theme
}

function applyTheme(theme: string) {
  const htmlElement = document.documentElement
  const resolved = resolveTheme(theme)

  if (resolved === 'dark') {
    htmlElement.classList.add('dark')
    htmlElement.setAttribute('data-theme', 'dark')
  } else {
    htmlElement.classList.remove('dark')
    htmlElement.removeAttribute('data-theme')
  }

  log.debug('[useThemeSync] Theme applied', { theme, resolved })
}

export function useThemeSync(): void {
  const store = useWorkspaceStore()

  // Apply initial theme
  applyTheme(store.theme || 'auto')

  // Watch for theme changes from Cockpit-Vue
  watch(() => store.theme, (newTheme) => {
    applyTheme(newTheme || 'auto')
  })

  // Listen for OS-level theme changes when theme='auto'
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  const handleSystemChange = () => {
    if (store.theme === 'auto') {
      applyTheme('auto')
    }
  }
  mediaQuery.addEventListener('change', handleSystemChange)
  onUnmounted(() => mediaQuery.removeEventListener('change', handleSystemChange))
}
