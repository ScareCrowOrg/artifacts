/**
 * Vitest Configuration for Artifacts (Canonical Cell Types)
 *
 * Self-contained config within artifacts/ — no dependency on cockpit-vue.
 * Cell types extending BaseCell resolve @/types and @/utils via shared/.
 * Service and config imports are stubbed (tests override with vi.mock).
 *
 * Usage (from repo root):
 *   npx vitest run --config artifacts/vitest.config.js
 *
 * Usage (from artifacts/ dir):
 *   npx vitest run
 */

import { defineConfig } from 'vitest/config'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: [
      './canonical/cell_types/**/tests/**/*.spec.ts',
      './canonical/cell_types/**/tests/**/*.test.ts',
    ],
  },
  resolve: {
    alias: {
      // Cell implementations reference shared types/utils
      '@/types': path.resolve(__dirname, 'shared/types'),
      '@/utils': path.resolve(__dirname, 'shared/utils'),
      // Stubs — real implementations are provided by vi.mock() in each test
      '@/services/apiService.js': path.resolve(__dirname, 'tests/stubs/apiService.js'),
      '@/config/endpoints.js': path.resolve(__dirname, 'tests/stubs/endpoints.js'),
    },
  },
  coverage: {
    provider: 'v8',
    include: ['**/cell_types/**/*Cell.ts'],
    exclude: ['**/*.vue', '**/tests/**', '**/node_modules/**'],
  },
})
