/**
 * shared/services/apiService.ts
 *
 * Shared authenticated HTTP utility for all viewers and cell types.
 *
 * Exports:
 * - `apiFetch` — ready-to-use fetch wrapper that lazy-reads the session token
 *   from the shared `workspaceStore`. Zero boilerplate in callers.
 *
 * Usage:
 * ```typescript
 * import { apiFetch } from '@/services/apiService'
 * const response = await apiFetch('/layout-books', { method: 'POST', body: JSON.stringify(data) })
 * if (!response.ok) throw new Error(`HTTP ${response.status}`)
 * const book = await response.json()
 * ```
 *
 * Design notes:
 * - `apiFetch` reads the token at call time (not at import time) so it always
 *   reflects the current session, even when the store hydrates after module load.
 * - `useWorkspaceStore()` is called inside the function body to avoid circular
 *   dependency issues and to ensure Pinia is already installed at call time.
 * - Base URL is read from `VITE_API_BASE_URL` env var (required, no fallback).
 *   Must be configured in .env or passed via docker-compose.
 * - This file lives in `artifacts/shared/` (alias `@/services`) so all viewers
 *   and cell types can import it without depending on viewer internals.
 */

import { useWorkspaceStore } from '@/stores/workspaceStore'

// ── Error types ────────────────────────────────────────────────────────────────

/**
 * Custom error class for session expiration.
 * Used by legacy cells and composables that handle auth failures.
 */
export class SessionExpiredError extends Error {
  constructor(message = 'Session expired or invalid token') {
    super(message)
    this.name = 'SessionExpiredError'
  }
}

// ── URL resolution ────────────────────────────────────────────────────────────

/**
 * Resolve the API base URL from configured sources (in order of priority):
 * 1. window.API_BASE_URL (runtime config)
 * 2. VITE_API_BASE_URL environment variable (from .env)
 *
 * @returns The API base URL (without trailing slash)
 * @throws {Error} if no API base URL is configured
 */
export function getApiBaseUrl(): string {
  // Check for window configuration first (runtime config set at index.html)
  if (typeof window !== 'undefined' && (window as any).API_BASE_URL) {
    return (window as any).API_BASE_URL
  }

  // Check for Vite environment variable (VITE_API_BASE_URL from .env)
  if (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) {
    return (import.meta as any).env.VITE_API_BASE_URL
  }

  throw new Error(
    '[apiService] No API base URL configured. ' +
    'Set window.API_BASE_URL at runtime or VITE_API_BASE_URL in .env'
  )
}

// Internal alias for backward compatibility
function getBaseUrl(): string {
  return getApiBaseUrl()
}

// ── Response parsing ──────────────────────────────────────────────────────────

async function parseResponse(response: Response): Promise<any> {
  if (response.status === 204) {
    return null
  }

  if (!response.ok) {
    let detail = 'Unknown error'
    try {
      const body = await response.json()
      detail = body?.detail ?? JSON.stringify(body)
    } catch {
      detail = await response.text().catch(() => 'Unknown error')
    }
    throw new Error(`HTTP ${response.status}: ${detail}`)
  }

  return response.json()
}

// ── Standalone apiFetch ───────────────────────────────────────────────────────

/**
 * Authenticated fetch that lazy-reads the session token from workspaceStore.
 *
 * The token is read at call time (not at import time), so it always reflects
 * the current session even when the store hydrates after module load.
 *
 * Returns the raw `Response` — callers handle `.json()` and error parsing.
 *
 * @throws {Error} if no session token is available when called.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  // Called inside the function body (not at module scope) to ensure Pinia is
  // already installed and to avoid potential circular dependency issues.
  const store = useWorkspaceStore()
  const token = store.sessionToken

  if (!token) {
    throw new Error('[apiService] No session token available')
  }

  // Backward compatibility: normalize path to avoid double /api prefix
  // Old format: /api/endpoint → /api/endpoint
  // New format: /endpoint → /api/endpoint
  const normalizedPath = path.startsWith('/api/') ? path : `/api${path}`
  const url = `${getBaseUrl()}${normalizedPath}`

  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  })
}

// ── Default export (backward compatibility with legacy imports) ────────────────

/**
 * Default export for backward compatibility with `import apiService from '@/services/apiService'`
 * Used by legacy cells and composables from cockpit-vue context.
 */
export default {
  fetch: apiFetch,
}
