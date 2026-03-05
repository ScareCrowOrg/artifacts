/**
 * shared/services/apiService.ts
 *
 * Shared HTTP utility for dynamic-workspace viewers.
 *
 * Provides `apiFetch` — a thin fetch wrapper that:
 * 1. Resolves paths relative to `VITE_CENTRALHUB_URL` so requests go through
 *    the Nginx proxy (no hardcoded ports).
 * 2. Attaches `Authorization: Bearer <token>` from the provided token.
 * 3. Parses JSON responses and throws descriptive errors on non-2xx status.
 * 4. Returns `null` for 204 No Content.
 *
 * Usage (in dynamic-workspace composables):
 * ```typescript
 * import { createApiFetch } from '@/services/apiService'
 * const apiFetch = createApiFetch(() => workspaceStore.sessionToken)
 * const book = await apiFetch('/layout-books', { method: 'POST', body: JSON.stringify(data) })
 * ```
 *
 * Design notes:
 * - The token is read lazily (via a getter) so it always reflects the current
 *   session, even if the store hydrates after the composable is created.
 * - Base URL is read from `VITE_CENTRALHUB_URL` env var; falls back to
 *   `http://localhost:8000` for local development.
 * - This file lives in `artifacts/shared/` (alias `@/services`) so all viewers
 *   can import it without depending on cockpit-vue internals.
 */

// ── URL resolution ────────────────────────────────────────────────────────────

function getBaseUrl(): string {
  return (
    (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_CENTRALHUB_URL) ||
    'http://localhost:8000'
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

// ── Factory ───────────────────────────────────────────────────────────────────

/**
 * Create an authenticated fetch function for a specific token source.
 *
 * @param getToken  Lazy getter for the Bearer token (e.g. `() => store.sessionToken`).
 *                  Called on every request so token changes are reflected immediately.
 * @returns         A fetch wrapper that resolves paths relative to `VITE_CENTRALHUB_URL`,
 *                  injects the Authorization header, and parses JSON responses.
 */
export function createApiFetch(getToken: () => string) {
  return async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
    const token = getToken()
    if (!token) {
      throw new Error('[apiService] No auth token available')
    }

    const url = `${getBaseUrl()}/api${path}`

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers ?? {}),
      },
    })

    return parseResponse(response)
  }
}
