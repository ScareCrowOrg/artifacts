/**
 * i18n/index.ts
 *
 * vue-i18n setup for DynamicWorkspace v2 viewer.
 * Creates a standalone i18n instance (not shared with Cockpit).
 */

import { createI18n } from 'vue-i18n'
import en from './en.json'
import pt from './pt-BR.json'

export const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, pt },
})

export default i18n
