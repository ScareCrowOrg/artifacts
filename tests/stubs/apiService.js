/**
 * Stub for @/services/apiService.js
 *
 * Exists only so vitest can resolve the import specifier in vi.mock().
 * The actual mock is defined in each test file via vi.mock factory.
 */
export default {
  fetch: () => Promise.reject(new Error('Stub — must be mocked in test')),
}
