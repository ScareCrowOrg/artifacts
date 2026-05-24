/**
 * i18nUtils.ts
 *
 * Shared i18n utilities. Single source of truth for locale normalization
 * used by cellI18nLoader, useLocaleSync, useAutoLoadCellI18n, and viewers.
 */

const localeMap: Record<string, string> = {
  'en-US': 'en',
  'en-GB': 'en',
  'en-AU': 'en',
  'en': 'en',
  'pt-BR': 'pt-BR',
  'pt-PT': 'pt-BR',
  'pt': 'pt-BR',
}

export function normalizeLocale(locale: string): string {
  return localeMap[locale] || locale
}
