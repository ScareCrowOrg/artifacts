/**
 * I18n Configuration for ScareVerse Cockpit
 * 
 * This module sets up internationalization support using vue-i18n.
 * Currently supports Portuguese (pt-BR) and English (en-US).
 * 
 * Technical terms in code remain in English.
 * User-facing strings are localized.
 */

import { createI18n } from 'vue-i18n'
import ptBR from './locales/pt-BR.json'
import enUS from './locales/en-US.json'

/**
 * Create and configure i18n instance
 * 
 * Default locale: pt-BR (Brazilian Portuguese)
 * Fallback locale: en-US (English)
 */
const i18n = createI18n({
  legacy: false, // Use Composition API mode
  locale: 'pt-BR', // Default language
  fallbackLocale: 'en-US', // Fallback language
  messages: {
    'pt-BR': ptBR,
    'en-US': enUS
  },
  // Enable global injection
  globalInjection: true,
  // Missing translation handler
  missingWarn: true,
  fallbackWarn: false
})

// PERMANENTE: log registered locale codes at startup for debugging
console.debug('[i18n-PERMANENTE] i18n startup: locale=' + String(i18n.global.locale.value) + ', fallbackLocale=en-US, registeredLocales=[pt-BR, en-US]')

export default i18n

/**
 * Available locales
 */
export const AVAILABLE_LOCALES = [
  {
    code: 'pt-BR',
    name: 'Português (Brasil)',
    flag: '🇧🇷'
  },
  {
    code: 'en-US',
    name: 'English (US)',
    flag: '🇺🇸'
  }
]

/**
 * Get current locale
 */
export function getCurrentLocale() {
  return i18n.global.locale.value
}

/**
 * Set locale
 * @param {string} locale - Locale code (e.g., 'pt-BR', 'en-US')
 */
export function setLocale(locale) {
  if (AVAILABLE_LOCALES.some(l => l.code === locale)) {
    i18n.global.locale.value = locale
    // Store preference in localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('scareverse-locale', locale)
    }
  }
}

/**
 * Load locale from localStorage or browser preference
 */
export function loadLocalePreference() {
  if (typeof window !== 'undefined') {
    // Check localStorage first
    const stored = localStorage.getItem('scareverse-locale')
    if (stored && AVAILABLE_LOCALES.some(l => l.code === stored)) {
      setLocale(stored)
      return
    }
    
    // Check browser language
    const browserLang = navigator.language
    if (browserLang.startsWith('pt')) {
      setLocale('pt-BR')
    } else {
      setLocale('en-US')
    }
  }
}
