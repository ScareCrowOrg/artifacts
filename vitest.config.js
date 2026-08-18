/**
 * Vitest Configuration for Artifacts (Canonical Cell Types)
 *
 * Self-contained config within artifacts/ — no dependency on cockpit-vue.
 * Cell types extending BaseCell resolve @/types and @/utils via shared/.
 * Service and config imports are stubbed (tests override with vi.mock).
 *
 * Usage (from artifacts/ dir — REQUIRED):
 *   npx vitest run
 *
 * ⚠️ `npx vitest run --config artifacts/vitest.config.js` from the repo root FAILS
 * ("No test files found") — `test.include` is resolved relative to the cwd (root),
 * not the config file location. Run from artifacts/ instead.
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
      // usePartyCalls (shared composable) lives in shared/composables/__tests__/,
      // outside the canonical/cell_types glob.  Wired in so `npx vitest run`
      // covers it.  (Other __tests__/ files, ex: useBaseViewer.test.ts, are NOT
      // wired because they still have unresolved @/stores imports — see
      // party-calls-modularization PR review finding #11.)
      './shared/composables/__tests__/usePartyCalls.test.ts',
      // Bug-hardening suite (issue party-calls-bug-hardening): G1/F1-F11.
      './shared/composables/__tests__/usePartyCalls.bugHardening.test.ts',
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
      // Subpath imports (mirror of vite.config.ts) — needed by shared composable
      // tests (ex: usePartyCalls.test.ts mocks #artifacts/shared/services/apiService)
      '#artifacts': __dirname,
      '#shared': path.resolve(__dirname, 'shared'),
      '#canonical': path.resolve(__dirname, 'canonical'),
      '#runtime': path.resolve(__dirname, 'runtime'),
      '#sandbox': path.resolve(__dirname, 'sandbox'),
    },
  },
  coverage: {
    provider: 'v8',
    include: ['**/cell_types/**/*Cell.ts'],
    exclude: ['**/*.vue', '**/tests/**', '**/node_modules/**'],
  },
})
