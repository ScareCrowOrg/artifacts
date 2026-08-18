/**
 * @file party-calls/http.ts
 * @description HTTP/transport helpers for the usePartyCalls composable
 * (Cloudflare Calls / WebRTC).  Extracted VERBATIM from the former monolithic
 * ``usePartyCalls.ts`` (section "HTTP helpers").  Stateless.
 *
 * Dependency graph: imports ``log`` from ``./state``.  No reverse imports.
 * See ``party-calls/README.md``.
 */

import { apiFetch } from '#artifacts/shared/services/apiService'
import { log } from './state'

// ─────────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ─────────────────────────────────────────────────────────────────────────────

/** Thin wrapper around apiFetch that throws with the server's error detail. */
export async function _apiFetchJson(path: string, options: RequestInit = {}): Promise<any> {
  const resp = await apiFetch(path, options)
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body.detail) detail = body.detail
    } catch { /* ignore parse errors */ }
    throw new Error(detail)
  }
  return resp.json()
}

/**
 * Poll the async provision task until it completes or fails.
 *
 * F8 FIX (bug-hardening): a transient HTTP error mid-poll (502/404/5xx — a
 * proxy/gateway blip while the provision task is still running) is RETRIED with
 * backoff instead of aborting the call; only a definitive task failure
 * (``status: 'failed'``) aborts.  A hard global time budget (< 200s) bounds the
 * loop and surfaces a descriptive error instead of polling forever.
 */
export async function _pollProvisionTask(
  taskId: string,
  maxRetries = 100,
  intervalMs = 2000,
  timeoutMs = 180_000,
): Promise<{ app_id: string }> {
  const startedAt = Date.now()
  for (let i = 0; i < maxRetries; i++) {
    if (Date.now() - startedAt >= timeoutMs) break
    try {
      const resp = await _apiFetchJson(`/calls/provision/${taskId}`)
      if (resp.status === 'completed') {
        log.debug('[pollProvision] task completed, app_id=%s', resp.app_id)
        return { app_id: resp.app_id }
      }
      if (resp.status === 'failed') {
        throw new Error(`Provision failed: ${resp.error || 'Unknown provision error'}`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      // Definitive failure → rethrow (aborts the call with a descriptive error).
      if (msg.startsWith('Provision failed')) throw err
      // Transient HTTP/network error mid-poll → retry with backoff (the task is
      // still provisioning; a 502 blip must not kill a call about to complete).
      log.warn('[pollProvision] transient error mid-poll attempt=%d: %s', i, msg)
      await new Promise(resolve => setTimeout(resolve, Math.min(intervalMs + i * 500, 10_000)))
      continue
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs))
  }
  throw new Error('Provision timeout — task did not complete within the retry limit')
}

/** Execute a party-cell backend action via execute-ephemeral (best-effort). */
export async function _executePartyAction(input: Record<string, unknown>): Promise<void> {
  try {
    const resp = await apiFetch('/api/cells/execute-ephemeral', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cell_type: 'party-cell', input_data: input }),
    })
    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      log.warn('[partyAction] action=%s failed (%s): %s', input.action, resp.status, text)
    }
  } catch (err) {
    log.warn('[partyAction] action=%s error: %s', input.action,
      err instanceof Error ? err.message : String(err))
  }
}
