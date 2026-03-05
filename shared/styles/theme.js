/**
 * ScareVerse Design System - Theme Manager
 *
 * JavaScript API for managing theme switching.
 */

import { createLogger } from '@/utils/logger'

const log = createLogger('theme')
const THEME_STORAGE_KEY = 'scareverse-theme'

export const THEMES = {
  LIGHT: 'light',
  DARK: 'dark',
  AUTO: 'auto',
}

/**
 * Get the current theme preference from localStorage
 */
export function getSavedTheme() {
  return localStorage.getItem(THEME_STORAGE_KEY) || THEMES.AUTO
}

/**
 * Save theme preference to localStorage
 */
export function saveTheme(theme) {
  if (!Object.values(THEMES).includes(theme)) {
    log.warn(`Invalid theme: ${theme}. Using AUTO.`)
    theme = THEMES.AUTO
  }
  localStorage.setItem(THEME_STORAGE_KEY, theme)
}

/**
 * Get system theme preference
 */
export function getSystemTheme() {
  if (
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  ) {
    return THEMES.DARK
  }
  return THEMES.LIGHT
}

/**
 * Get the effective theme to apply (resolves AUTO to actual theme)
 */
export function getEffectiveTheme(preferredTheme = null) {
  const theme = preferredTheme || getSavedTheme()

  if (theme === THEMES.AUTO) {
    return getSystemTheme()
  }

  return theme
}

/**
 * Apply theme to document
 */
export function applyTheme(theme) {
  const effectiveTheme = getEffectiveTheme(theme)
  document.documentElement.setAttribute('data-theme', effectiveTheme)

  // Save preference if it's not auto
  if (theme !== THEMES.AUTO) {
    saveTheme(theme)
  }

  return effectiveTheme
}

/**
 * Initialize theme on app load
 */
export function initTheme() {
  const savedTheme = getSavedTheme()
  return applyTheme(savedTheme)
}

/**
 * Toggle between light and dark themes
 */
export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme')
  const newTheme = current === THEMES.DARK ? THEMES.LIGHT : THEMES.DARK
  applyTheme(newTheme)
  saveTheme(newTheme)
  return newTheme
}

/**
 * Listen for system theme changes when AUTO mode is active
 */
export function watchSystemTheme(callback) {
  if (!window.matchMedia) return

  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

  const handler = (e) => {
    const savedTheme = getSavedTheme()
    if (savedTheme === THEMES.AUTO) {
      const newTheme = e.matches ? THEMES.DARK : THEMES.LIGHT
      applyTheme(THEMES.AUTO)
      if (callback) callback(newTheme)
    }
  }

  mediaQuery.addEventListener('change', handler)

  // Return cleanup function
  return () => {
    mediaQuery.removeEventListener('change', handler)
  }
}

/**
 * Composable for Vue components
 */
export function useTheme() {
  return {
    themes: THEMES,
    getSavedTheme,
    saveTheme,
    getSystemTheme,
    getEffectiveTheme,
    applyTheme,
    toggleTheme,
    watchSystemTheme,
  }
}

export default {
  THEMES,
  getSavedTheme,
  saveTheme,
  getSystemTheme,
  getEffectiveTheme,
  applyTheme,
  initTheme,
  toggleTheme,
  watchSystemTheme,
  useTheme,
}
