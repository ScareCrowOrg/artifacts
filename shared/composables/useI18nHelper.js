/**
 * Composable for using i18n in components
 * 
 * This composable provides easy access to translation functions
 * and locale management in Vue components.
 * 
 * @example
 * ```vue
 * <script setup>
 * import { useI18nHelper } from '@/composables/useI18nHelper'
 * 
 * const { t, locale, availableLocales, changeLocale } = useI18nHelper()
 * </script>
 * 
 * <template>
 *   <div>
 *     <h1>{{ t('cells.title') }}</h1>
 *     <button @click="changeLocale('en-US')">English</button>
 *   </div>
 * </template>
 * ```
 */

import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { AVAILABLE_LOCALES, setLocale } from '@/i18n'

export function useI18nHelper() {
  const { t, locale } = useI18n()
  
  /**
   * Change the current locale
   * @param {string} newLocale - Locale code (e.g., 'pt-BR', 'en-US')
   */
  const changeLocale = (newLocale) => {
    setLocale(newLocale)
  }
  
  /**
   * Get available locales
   */
  const availableLocales = computed(() => AVAILABLE_LOCALES)
  
  /**
   * Get current locale code
   */
  const currentLocale = computed(() => locale.value)
  
  /**
   * Translate with parameters
   * @param {string} key - Translation key
   * @param {object} params - Parameters for interpolation
   * @returns {string} Translated string
   * 
   * @example
   * tp('messages.createSuccess', { entity: 'Cell' })
   */
  const tp = (key, params) => {
    return t(key, params)
  }
  
  /**
   * Translate entity name based on context
   * @param {string} entity - Entity type (e.g., 'cell', 'book')
   * @returns {string} Translated entity name
   */
  const te = (entity) => {
    const entityMap = {
      cell: 'cells.title',
      book: 'books.title',
      fragment: 'fragments.title'
    }
    return t(entityMap[entity] || entity)
  }
  
  /**
   * Get error message
   * @param {string|object} error - Error key or error response object
   * @returns {string} Translated error message
   */
  const getErrorMessage = (error) => {
    // If error is an object with i18n_key
    if (error && typeof error === 'object' && error.i18n_key) {
      return t(error.i18n_key, error.details || {})
    }
    
    // If error is a string key
    if (typeof error === 'string') {
      return t(`errors.${error}`)
    }
    
    // Default error message
    return t('errors.generic')
  }
  
  return {
    t,
    tp,
    te,
    locale: currentLocale,
    availableLocales,
    changeLocale,
    getErrorMessage
  }
}
