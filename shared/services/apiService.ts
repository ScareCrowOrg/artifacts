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
 * - Base URL is read from `VITE_BACKEND_URL` env var; falls back to
 *   `http://localhost:5050` for local development (ScareRunner Backend).
 * - This file lives in `artifacts/shared/` (alias `@/services`) so all viewers
 *   and cell types can import it without depending on viewer internals.
 */

import { useWorkspaceStore } from '@/stores/workspaceStore'

// ── URL resolution ────────────────────────────────────────────────────────────

function getBaseUrl(): string {
  return (
    (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_BACKEND_URL) ||
    'http://localhost:5050'
  )
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

  const url = `${getBaseUrl()}/api${path}`

  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  })
}
