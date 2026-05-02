/**
 * @file distributedState.ts
 * @description TypeScript interfaces for the useDistributedState protocol.
 *
 * Defines the message envelope format and options used by the
 * useDistributedState composable for bi-directional synchronisation
 * between a Pinia store branch and a Redis L1 channel via WSS.
 *
 * Protocol overview:
 *   Client → Server: snapshot_request  (on connect, to prime the local store)
 *   Server → Client: snapshot          (full state for the requested branch)
 *   Server → Client: patch             (differential update — JSON Patch RFC 6902)
 *   Client → Server: patch             (local mutation propagated to other peers)
 *   Both directions: heartbeat         (keep-alive, no payload processing required)
 */

// ─────────────────────────────────────────────────────────────────────────────
// JSON Patch (RFC 6902)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * A single JSON Patch operation (RFC 6902).
 * Used for differential state updates to minimise WebSocket traffic.
 */
export interface JsonPatchOperation {
  /** Operation type */
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test'

  /** JSON Pointer (RFC 6901) path to the target location */
  path: string

  /** Value for add / replace / test operations */
  value?: unknown

  /** Source path for move / copy operations */
  from?: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Message payloads
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Snapshot payload — sent from server to client in response to a
 * snapshot_request message, or as an initial state push.
 *
 * @template S  Shape of the store branch being synchronised.
 */
export interface DistributedSnapshotPayload<S = unknown> {
  /** Full current state of the synchronised branch */
  state: S
}

/**
 * Patch payload — differential update using JSON Patch (RFC 6902).
 * May be sent in either direction (client → server or server → client).
 */
export interface DistributedPatchPayload {
  /** Store branch name (e.g. "messages", "typing") */
  branch: string

  /** Ordered list of patch operations to apply */
  operations: JsonPatchOperation[]
}

// ─────────────────────────────────────────────────────────────────────────────
// Message envelope
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Generic envelope for all messages sent over the WSS channel.
 *
 * @template T  Payload type — one of the Distributed*Payload interfaces above,
 *              or `undefined` for snapshot_request / heartbeat messages.
 */
export interface DistributedStateMessage<T = unknown> {
  /** Discriminant tag for the message type */
  type: 'patch' | 'snapshot' | 'snapshot_request' | 'heartbeat'

  /**
   * Isolates the channel from other instances.
   * Typically formatted as "{cell-type}:{partyId}", e.g. "planet-chat:abc123".
   */
  contextId: string

  /**
   * Identifies the originating user or AI agent.
   * Used for conflict resolution and audit trails.
   */
  senderId: string

  /**
   * Unix timestamp in milliseconds (epoch).
   * Used for Last-Write-Wins (LWW) conflict resolution.
   */
  timestamp: number

  /** Type-safe message payload */
  payload: T
}

// ─────────────────────────────────────────────────────────────────────────────
// Conflict tracking
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Describes a write conflict detected when two peers update the same
 * store branch concurrently.
 *
 * In v1 this is informational only — the resolution outcome is determined
 * by the `conflictStrategy` option set on the composable.
 */
export interface DistributedWriteConflict {
  /** Store branch where the conflict occurred */
  branch: string

  /** Timestamp of the local (outgoing) write attempt */
  localTimestamp: number

  /** Timestamp of the remote (incoming) write that conflicts */
  remoteTimestamp: number

  /** Resolution strategy that was applied */
  strategy: 'lww' | 'append'
}

// ─────────────────────────────────────────────────────────────────────────────
// Composable options
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Options accepted by the `useDistributedState` composable.
 *
 * @template S  Shape of the Pinia store returned by the store factory.
 */
export interface UseDistributedStateOptions<S extends Record<string, unknown> = Record<string, unknown>> {
  /**
   * Unique identifier that scopes this connection to a specific context.
   * Used as the WSS channel query-param value, e.g.:
   *   `/wss/events?channel=planet-chat:${contextId}`
   */
  contextId: string

  /**
   * Pinia store instance (return value of the store factory call).
   * The composable will read/write the `branch` key on this store.
   */
  store: S

  /**
   * Key of the store property to synchronise.
   * Must be a top-level key of `S`.
   */
  branch: keyof S & string

  /**
   * Conflict resolution strategy.
   *
   * - `'append'`  — Append-only; ideal for chat history where every message
   *                  must be preserved.  Two simultaneous writes keep both.
   * - `'lww'`     — Last-Write-Wins; the most recently timestamped patch wins.
   *                  Suitable for single-value fields like `typing` indicators.
   *
   * Defaults to `'lww'`.
   */
  conflictStrategy?: 'lww' | 'append'
}
