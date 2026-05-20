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
 * Normalize path to complete URL based on pattern:
 * - If path starts with `/` and contains `/api/` → baseUrl + path
 * - If path starts with `/` and NO `/api/` → baseUrl/api + path
 * - If path doesn't start with `/` → use as-is (already complete URL)
 *
 * @param path Request path or URL
 * @returns Complete URL
 */
export function normalizePath(path: string): string {
  // If doesn't start with /, assume it's already a complete URL
  if (!path.startsWith('/')) {
    return path
  }

  const baseUrl = getApiBaseUrl()

  // If path already contains /api/, concatenate as-is
  if (path.includes('/api/')) {
    return `${baseUrl}${path}`
  }

  // If path doesn't have /api/, add it
  return `${baseUrl}/api${path}`
}

/**
 * Resilient authenticated fetch.
 *
 * Auth strategy:
 * - Reads Bearer token from workspaceStore (Pinia) at call time
 * - Always sends Authorization header when token is available
 *
 * This single function serves all viewers and cell types. Since CentralHub
 * is always present, Pinia + workspaceStore are always available, and the
 * token is always set via the MFE handshake (INIT_WORKSPACE postMessage).
 * Cookie fallback was removed as dead code — see unified-mfe-handshake-refactor.
 *
 * Path normalization:
 * - `/layout-books` → http://localhost:5050/api/layout-books
 * - `/api/ai-models/config` → http://localhost:5050/api/ai-models/config
 * - `http://localhost:5050/api/...` → used as-is
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  // Read Bearer token from workspaceStore (Pinia).
  // Since CentralHub is always present, Pinia + workspaceStore are always
  // available, and the token is set via the MFE handshake.
  const store = useWorkspaceStore()
  const token = store.sessionToken

  const url = normalizePath(path)
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  return fetch(url, { ...options, headers })
}

// ── Default export (backward compatibility with legacy imports) ────────────────

/**
 * Default export for backward compatibility with `import apiService from '@/services/apiService'`
 * DEPRECATED: Use `import { apiFetch } from '@/services/apiService'` instead
 *
 * apiFetch automatically normalizes paths:
 * - `/path` → ${baseUrl}/api/path
 * - `/api/path` → ${baseUrl}/api/path
 * - `http://...` → used as-is
 */
export default {
  fetch: apiFetch,
}
