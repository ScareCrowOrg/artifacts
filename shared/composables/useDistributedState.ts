/**
 * @file useDistributedState.ts
 * @description Vue 3 composable for bi-directional distributed state
 * synchronisation between a Pinia store branch and a Redis L1 channel
 * via the existing `/wss/events` WebSocket endpoint.
 *
 * ## Usage
 * ```typescript
 * const { isConnected, connectionError } = useDistributedState({
 *   contextId: `planet-chat:${partyId}`,
 *   store: usePlanetChatStore(),
 *   branch: 'messages',
 *   conflictStrategy: 'append',
 * })
 * ```
 *
 * ## Protocol
 * 1. On mount   → connect to `ws://.../wss/events?channel={contextId}`
 *                  → send `snapshot_request`
 * 2. On message `snapshot` → replace `store[branch]` with payload.state
 * 3. On message `patch`    → apply JSON Patch operations to `store[branch]`
 * 4. On local `store[branch]` mutation → send patch diff to the channel
 * 5. On unmount → close WebSocket, cancel watchers
 *
 * ## Conflict resolution
 * - `'append'`  Append-only for lists (chat history). Both concurrent writes survive.
 * - `'lww'`     Last-Write-Wins for scalar / single-value branches.
 */

import { ref, watch, computed, onMounted, onUnmounted, type WatchStopHandle } from 'vue'
import type {
  UseDistributedStateOptions,
  DistributedStateMessage,
  DistributedPatchPayload,
  DistributedSnapshotPayload,
  JsonPatchOperation,
} from '@/types/distributedState'

// ─────────────────────────────────────────────────────────────────────────────
// JSON Patch helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply a list of RFC 6902 JSON Patch operations to a value.
 *
 * We implement a minimal subset — `add`, `remove`, `replace` — which covers
 * all operations emitted by the planet-chat-cell backend.
 *
 * For `add` with path ending in `/-`, the value is appended to the array.
 *
 * @param target  The value to patch (will be mutated in-place when possible).
 * @param ops     Ordered list of patch operations.
 * @returns The patched value (may be a new reference for scalar replacements).
 */
function applySimplePatch(target: unknown, ops: JsonPatchOperation[]): unknown {
  let current: unknown = target

  for (const op of ops) {
    const parts = op.path.split('/').filter((p) => p !== '')

    if (op.op === 'add' && parts.length > 0 && parts[parts.length - 1] === '-') {
      // Append to array: /some/path/-
      const arrPath = parts.slice(0, -1)
      const arr = arrPath.length === 0 ? current : _get(current, arrPath)
      if (Array.isArray(arr)) {
        arr.push(op.value)
      }
    } else if (op.op === 'add' || op.op === 'replace') {
      if (parts.length === 0) {
        current = op.value
      } else {
        _set(current, parts, op.value)
      }
    } else if (op.op === 'remove') {
      if (parts.length > 0) {
        _remove(current, parts)
      }
    }
    // move, copy, test — not needed for v1
  }

  return current
}

function _get(obj: unknown, parts: string[]): unknown {
  let cur: unknown = obj
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[p]
  }
  return cur
}

function _set(obj: unknown, parts: string[], value: unknown): void {
  if (parts.length === 0 || obj == null || typeof obj !== 'object') return
  const last = parts[parts.length - 1]
  const parent = _get(obj, parts.slice(0, -1))
  if (parent != null && typeof parent === 'object') {
    ;(parent as Record<string, unknown>)[last] = value
  }
}

function _remove(obj: unknown, parts: string[]): void {
  if (parts.length === 0 || obj == null || typeof obj !== 'object') return
  const last = parts[parts.length - 1]
  const parent = _get(obj, parts.slice(0, -1))
  if (parent == null || typeof parent !== 'object') return
  if (Array.isArray(parent)) {
    const idx = parseInt(last, 10)
    if (!isNaN(idx)) parent.splice(idx, 1)
  } else {
    delete (parent as Record<string, unknown>)[last]
  }
}

/**
 * Produce a minimal set of JSON Patch operations that transform `prev` into
 * `next` for an append-only array (chat messages).  For LWW branches we emit
 * a single `replace` at the root of the branch.
 */
function diffToPatch(
  branch: string,
  prev: unknown,
  next: unknown,
  strategy: 'append' | 'lww',
): JsonPatchOperation[] {
  if (strategy === 'append' && Array.isArray(prev) && Array.isArray(next)) {
    if (next.length <= prev.length) return []
    return next.slice(prev.length).map((item) => ({
      op: 'add' as const,
      path: `/${branch}/-`,
      value: item,
    }))
  }
  // lww: replace the whole branch
  return [{ op: 'replace', path: `/${branch}`, value: next }]
}

// ─────────────────────────────────────────────────────────────────────────────
// Composable
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Reactive return value of `useDistributedState`.
 */
export interface UseDistributedStateReturn {
  /** `true` when the WebSocket connection is open */
  isConnected: ReturnType<typeof ref<boolean>>

  /** Last WebSocket/network error, or `null` */
  connectionError: ReturnType<typeof ref<string | null>>

  /** Manually disconnect (useful for testing or early teardown) */
  disconnect: () => void
}

/**
 * Composable that synchronises a Pinia store branch with a Redis L1 channel
 * via the `/wss/events` WebSocket endpoint.
 *
 * Must be called inside a Vue component's `setup()` (or `<script setup>`).
 */
export function useDistributedState<S extends Record<string, unknown>>(
  options: UseDistributedStateOptions<S>,
): UseDistributedStateReturn {
  const { store, branch, conflictStrategy = 'lww' } = options

  // Resolve contextId to a computed so reactive refs (ComputedRef / Ref) are
  // supported in addition to plain strings.  When the value changes (e.g. room
  // switching) the composable automatically disconnects and reconnects.
  const resolvedContextId = computed(() =>
    typeof options.contextId === 'string' ? options.contextId : options.contextId.value,
  )

  const isConnected = ref(false)
  const connectionError = ref<string | null>(null)

  let ws: WebSocket | null = null
  let stopWatcher: WatchStopHandle | null = null

  // Track the last known remote value to avoid echo-sending our own patches back
  let lastKnownRemote: unknown = undefined
  // Timestamp of the last patch we sent (for LWW)
  let lastSentTimestamp = 0

  // ── helpers ──────────────────────────────────────────────────────────────

  function buildWssUrl(): string {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    return `${proto}://${host}/wss/events?channel=${encodeURIComponent(resolvedContextId.value)}`
  }

  function sendJson(msg: Record<string, unknown>): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
    }
  }

  function sendSnapshotRequest(): void {
    const msg: DistributedStateMessage<undefined> = {
      type: 'snapshot_request',
      contextId: resolvedContextId.value,
      senderId: 'client',
      timestamp: Date.now(),
      payload: undefined,
    }
    sendJson(msg as unknown as Record<string, unknown>)
  }

  function handleMessage(raw: string): void {
    let msg: DistributedStateMessage<unknown>
    try {
      msg = JSON.parse(raw) as DistributedStateMessage<unknown>
    } catch {
      return
    }

    if (msg.type === 'heartbeat') return

    if (msg.contextId && msg.contextId !== resolvedContextId.value) return

    if (msg.type === 'snapshot') {
      const payload = msg.payload as DistributedSnapshotPayload<unknown>
      if (payload && 'state' in payload) {
        lastKnownRemote = payload.state
        ;(store as Record<string, unknown>)[branch] = payload.state
      }
      return
    }

    if (msg.type === 'patch') {
      const payload = msg.payload as DistributedPatchPayload
      if (!payload || !Array.isArray(payload.operations)) return

      // Resolve conflicts for LWW: skip if our local patch is newer
      if (conflictStrategy === 'lww' && msg.timestamp < lastSentTimestamp) return

      const currentBranchValue = (store as Record<string, unknown>)[branch]
      const patched = applySimplePatch(currentBranchValue, payload.operations)

      lastKnownRemote = patched
      ;(store as Record<string, unknown>)[branch] = patched
    }
  }

  // ── watcher that detects local mutations and sends patches ────────────────

  function startWatcher(): void {
    stopWatcher = watch(
      () => (store as Record<string, unknown>)[branch],
      (newVal, oldVal) => {
        // Skip if this change came from a remote message (we just applied it)
        if (newVal === lastKnownRemote) return

        const ops = diffToPatch(branch, oldVal, newVal, conflictStrategy)
        if (ops.length === 0) return

        const now = Date.now()
        lastSentTimestamp = now

        const patchMsg: DistributedStateMessage<DistributedPatchPayload> = {
          type: 'patch',
          contextId: resolvedContextId.value,
          senderId: 'client',
          timestamp: now,
          payload: {
            branch,
            operations: ops,
          },
        }
        sendJson(patchMsg as unknown as Record<string, unknown>)
      },
      { deep: true },
    )
  }

  // ── WebSocket lifecycle ───────────────────────────────────────────────────

  function connect(): void {
    try {
      ws = new WebSocket(buildWssUrl())

      ws.onopen = () => {
        isConnected.value = true
        connectionError.value = null
        sendSnapshotRequest()
        startWatcher()
      }

      ws.onmessage = (event: MessageEvent) => {
        handleMessage(event.data as string)
      }

      ws.onerror = () => {
        connectionError.value = `WebSocket error on channel: ${resolvedContextId.value}`
      }

      ws.onclose = () => {
        isConnected.value = false
        if (stopWatcher) {
          stopWatcher()
          stopWatcher = null
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to open WebSocket'
      connectionError.value = msg
    }
  }

  function disconnect(): void {
    if (stopWatcher) {
      stopWatcher()
      stopWatcher = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    isConnected.value = false
  }

  // ── lifecycle hooks ───────────────────────────────────────────────────────

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  // Reconnect automatically when the resolved contextId changes (e.g. room switch)
  watch(resolvedContextId, (newId, oldId) => {
    if (newId !== oldId) {
      disconnect()
      connect()
    }
  })

  return { isConnected, connectionError, disconnect }
}
