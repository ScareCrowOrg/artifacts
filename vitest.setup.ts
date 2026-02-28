/**
 * @file vitest.setup.ts
 * @description Vitest setup file for artifacts test suite
 * 
 * Provides global mocks and test utilities for BaseCell tests
 * SESSION 202602280319
 */

import { vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'

// Create a simple i18n instance for tests
const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {},
    pt: {}
  }
})

// Install i18n plugin globally for all Vue component tests
config.global.plugins = [i18n]

// Mock i18n for Vue Test Utils (backward compatibility)
config.global.mocks = {
  $t: (key: string) => key,
  $i18n: {
    locale: 'en',
    t: (key: string) => key
  }
}

// Mock console to reduce noise in tests
global.console = {
  ...console,
  // Keep error and warn for debugging
  // but suppress log and info
  log: vi.fn(),
  info: vi.fn()
}
