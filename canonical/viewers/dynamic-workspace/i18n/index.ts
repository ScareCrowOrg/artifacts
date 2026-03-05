/**
 * i18n/index.ts
 *
 * vue-i18n setup for DynamicWorkspace v2 viewer.
 * Creates a standalone i18n instance (not shared with Cockpit).
 */

import { createI18n } from 'vue-i18n'
import en from './en'

export const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en },
})

export default i18n
