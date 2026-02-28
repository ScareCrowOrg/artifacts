/**
 * @file vitest.setup.ts
 * @description Vitest setup file for artifacts test suite
 * 
 * Provides global mocks and test utilities for BaseCell tests
 * SESSION 202602280319
 */

import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Mock i18n plugin for Vue Test Utils
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
