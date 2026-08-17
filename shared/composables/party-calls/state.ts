/**
 * @file party-calls/state.ts
 * @description Centralized module-level state + invariant helpers for the
 * usePartyCalls composable (Cloudflare Calls / WebRTC).  Extracted VERBATIM
 * from the former monolithic ``usePartyCalls.ts`` (section "Module-level
 * state").  This is the shared state where the race bugs live (H3 / pending /
 * grace) — see ``.claude/rules/party-cell.md``.
 *
 * ESM singleton semantics are preserved exactly: the mutable scalar state lives
 * in the exported ``state`` object (single live object per bundle), read and
 * written directly by the domain modules as ``state._pc`` etc.  The collections
 * (Maps/Sets/WeakMap) are mutated via methods only (never reassigned), so they
 * stay ``export const`` bindings — same behaviour as the old module-level state.
 *
 * NOTE on why ``state`` is an object: TypeScript forbids reassigning an imported
 * ``let`` binding (TS2632 "Cannot assign to … because it is an import"), even
 * when the source module exports ``let``.  A mutable exported object is the
 * type-safe way to keep the "read/write directly" semantics of the original
 * module-level state without setter boilerplate.
 *
 * Dependency graph: leaf module (imports only ``@/utils/logger`` + partyStore
 * type).  See ``party-calls/README.md``.
 */

import { createLogger } from '@/utils/logger'
import type { TrackType } from '#artifacts/shared/stores/partyStore'

export const log = createLogger('composable:usePartyCalls')

// ─────────────────────────────────────────────────────────────────────────────
// Module-level state (shared across composable instances)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Mutable scalar state, reassigned directly by the domain modules (the old
 * module-level ``let`` bindings).  Collections that are only mutated via
 * methods (never reassigned) stay as named ``const`` exports below.
 */
export const state = {
  _pc: null as RTCPeerConnection | null,
  _localStream: null as MediaStream | null,
  _currentSessionId: null as string | null,
  _heartbeatTimer: null as number | null,
  /** The display stream being shared (screen/3D canvas) — stopped on hangUp. */
  _screenStream: null as MediaStream | null,
  /** Display-friendly TrackTypes this caller has published to the room
   *  (startCall base + 'screen' after shareStream) — kept so registry/presence
   *  updates carry the REAL track set (GAP 2). */
  _publishedTracks: [] as TrackType[],
  /** NATIVE track names (sender.track.id) this caller has published. */
  _publishedTrackNames: [] as string[],
  /** One-shot guard for the F2 (ITER_1) stats dump — H2: a video inbound-rtp
   *  with bytesReceived==0 ~5s after subscribe means the SFU resolved the
   *  subscription (mid 1, no errorCode) but is NOT forwarding video RTP to
   *  this subscriber (vs H1: the track is dropped client-side at the ontrack
   *  !stream guard). */
  _statsDumpScheduled: false,
  /** Monotonic seq for _refreshDiscovery entry/exit DIAGs (B4) — lets F3 prove
   *  concurrent interleavings (race H3) by correlating [start] seq=N with
   *  [end] seq=N on the SAME discovery pass. */
  _discoverySeq: 0,
  /** The native MediaStreamTrack id of the currently shared screen (if any) —
   *  used by stopSharing to detach the correct sender from the peer
   *  connection. */
  _screenTrackId: null as string | null,
  /** The sendonly screen transceiver orphaned by the last stopSharing
   *  (``sender.track`` nulled by ``removeTrack`` but the transceiver kept) —
   *  reused by the next shareStream via ``replaceTrack`` so each share/stop
   *  cycle does NOT stack a new transceiver (A1; avoids the SFU's 413
   *  accumulation error).  Captured explicitly because the old direction-only
   *  orphan search missed the transceiver once the last offer had re-negotiated
   *  its direction. */
  _orphanScreenTx: null as RTCRtpTransceiver | null,
  /** The recvonly transceivers created at join (audio/video) — kept so
   *  _enableLocalTrack can attach a local track and switch the matching one to
   *  'sendrecv' on the first opt-in click (Caso B: media opt-in, no capture on
   *  join).  Reset on hangUp. */
  _localAudioTx: null as RTCRtpTransceiver | null,
  _localVideoTx: null as RTCRtpTransceiver | null,
}

/** Native trackNames already subscribed per remote sessionId (GAP 3 — the
 *  heartbeat re-subscribes only the delta when a session adds a new track). */
export const _subscribedTrackNames = new Map<string, string[]>()
/** sessionId → { nativeTrackId → 'mic'|'camera'|'screen' } — lets
 *  _handleRemoteTrack tell a screen track apart from the camera (GAP 4). */
export const _remoteTrackTypes = new Map<string, Map<string, string>>()
/** mid (receiving transceiver) → {sessionId, trackName} for remote tracks,
 *  populated from the tracks/new remote response.  The mid is the ONLY reliable
 *  bridge to the publisher's native trackName — Cloudflare delivers the received
 *  track.id OPAQUE (no {sessionId}/{trackName} slash format), so the ontrack can
 *  classify via event.transceiver.mid against this map (F3 CICLO 4). */
export const _remoteMidToTrackName = new Map<string, { sessionId: string; trackName: string }>()
/** F3 FIX (ITER_1 H3): transceiver-scoped copy of the same classification —
 *  ``RTCRtpTransceiver`` → {sessionId, trackName}.  The ontrack fires from a
 *  STABLE RTCRtpTransceiver, but ``_remoteMidToTrackName`` is a mid-keyed GLOBAL
 *  Map that concurrent operations (prune removeOwnerMappings /
 *  removeScreenMapping, _teardownRemoteMedia, interleaved _refreshDiscovery
 *  across heartbeats) mutate BETWEEN the population and the ontrack firing.  In
 *  F7 ciclo 2 the video ontrack read the global Map with mid "1" already gone
 *  (despite a 2-entry mid_map populated) and fell back to the opaque stream.id —
 *  a separate generic tile instead of the publisher's tile.  Storing the
 *  classification ON the transceiver (WeakMap — no strong refs, GC-safe) makes
 *  the ontrack read the mapping that belongs to ITS transceiver, immune to the
 *  race. */
export const _transceiverMeta = new WeakMap<RTCRtpTransceiver, { sessionId: string; trackName: string }>()
/**
 * F3 FIX (ITER_1 guest-screenshare CICLO 2): mids whose remote subscription is
 * IN FLIGHT — the SFU tracks/new resolved the mid and ``_subscribeToRemoteTracks``
 * populated ``_remoteMidToTrackName`` / ``_transceiverMeta``, but the ontrack has
 * NOT fired yet.  Concurrent ``_refreshDiscovery`` prunes (removeOwnerMappings /
 * removeScreenMapping) must NOT drop those mids between the population and the
 * ontrack.  F7 ciclo 1 proved exactly this drop (race H3): the screen arrived on
 * the EXISTING video transceiver (mid 1), the first pass anchored its WeakMap
 * (transceiver_meta_sets=1), yet a concurrent prune dropped BOTH the WeakMap and
 * the global map before the ontrack, so the screen fell back to the opaque
 * stream.id and was pruned.  A mid leaves the set when its ontrack classifies,
 * or after ``_PENDING_SUBSCRIBE_TIMEOUT_MS`` (guard for a subscription whose
 * ontrack never fires — the timeout must never leak protected mids). */
export const _pendingSubscribeMids = new Set<string>()
export const _PENDING_SUBSCRIBE_TIMEOUT_MS = 5000

/**
 * F3 FIX (ITER_1 guest-screenshare CICLO 3): wall-clock time each remote-stream
 * tile key was last ADDED to `remoteStreams`.  Used as a GRACE-PERIOD guard in
 * `_cleanupEndedRemoteTrack`: a SPURIOUS end-of-track event (mute/ended fired by
 * Chrome on a STALE track riding a REUSED transceiver mid — confirmed in F7: the
 * screen tile entered _handleRemoteTrack and was removed in the SAME dispatch)
 * arrives within milliseconds of the ontrack.  A REAL end (publisher stops → SFU
 * reaper signals event=ended) arrives much later, so a ~400ms grace only blocks
 * the spurious same-dispatch removal and never defers a genuine teardown
 * meaningfully.  Entries are deleted when the tile is legitimately removed and
 * cleared on hangUp.
 */
export const _remoteStreamAddedAt = new Map<string, number>()
export const _REMOTE_STREAM_GRACE_MS = 400

/** Drop the transceiver-scoped meta for a mid, keeping the WeakMap in lockstep
 *  with ``_remoteMidToTrackName`` deletions (prune / teardown).  Safe to call
 *  for a mid whose transceiver is gone or whose meta was never set.  F3 FIX
 *  (CICLO 2): never drops a mid whose subscription is still in flight (pending)
 *  — the prune is a transient signal that can race the incoming screen. */
export function _dropTransceiverMeta(mid: string | null | undefined): void {
  if (!mid || !state._pc) return
  if (_pendingSubscribeMids.has(mid)) return
  const tx = state._pc.getTransceivers().find((t) => t.mid === mid)
  if (tx) _transceiverMeta.delete(tx)
}

/** F3 FIX (CICLO 2): protect the given mids (populated by a remote subscription)
 *  from concurrent prunes until their ontrack classifies or the timeout fires.
 *  One bounded 5s timer per mid, cleared by the ontrack — a timer firing for an
 *  already-cleared mid is a harmless no-op delete. */
export function _markMidsPending(mids: string[], sessionId: string): void {
  const added: string[] = []
  for (const mid of mids) {
    if (!mid || _pendingSubscribeMids.has(mid)) continue
    _pendingSubscribeMids.add(mid)
    added.push(mid)
    window.setTimeout(() => {
      _pendingSubscribeMids.delete(mid)
    }, _PENDING_SUBSCRIBE_TIMEOUT_MS)
  }
  if (added.length > 0) {
    log.warn('[DIAG][pending] marked mids=%j session=%s', added, sessionId)
  }
}

/** F3 FIX (CICLO 2): the ontrack for a pending mid fired and classified — the
 *  subscription has landed on a tile, so the pending protection is released. */
export function _unmarkMidPending(mid: string | null | undefined, sessionKey: string): void {
  if (mid && _pendingSubscribeMids.delete(mid)) {
    log.warn('[DIAG][pending] cleared on ontrack mid=%s sessionKey=%s', mid, sessionKey)
  }
}

/** F3 FIX (CICLO 2): does the owner have any subscription still in flight?  A
 *  ``removeOwnerMappings`` for such an owner is a stale concurrent snapshot (the
 *  tracks/new resolved, so the session IS active) — pruning would drop the
 *  just-populated map/WeakMap/_remoteTrackTypes of the incoming track. */
export function _ownerHasPendingMids(ownerId: string): boolean {
  for (const mid of _pendingSubscribeMids) {
    const info = _remoteMidToTrackName.get(mid)
    if (info?.sessionId === ownerId) return true
  }
  return false
}
/**
 * F3 FIX (ITER_1 guest-screenshare): re-anchor ``_transceiverMeta`` for a remote
 * session's mids AFTER the SFU offer has been applied at setRemoteDescription.
 *
 * The FIRST population pass (in _subscribeToRemoteTracks, before
 * setRemoteDescription) anchors only transceivers that already exist at that
 * instant — the recvonly audio/video transceivers created at join.  A track
 * added mid-call (the shared screen) gets its transceiver created ONLY when the
 * SFU's offer is applied at setRemoteDescription, so the first pass found
 * nothing and the WeakMap stayed EMPTY for the screen.  The screen's ontrack
 * then depends 100% on the global ``_remoteMidToTrackName`` — if a concurrent
 * discovery/prune drops that entry between the population and the ontrack
 * (race H3), the ontrack falls back to the opaque stream.id → generic tile →
 * pruned → the screen never renders (the guest→host asymmetry).
 *
 * ontrack handlers are dispatched as tasks AFTER setRemoteDescription resolves,
 * so this second pass (running in the ``await`` continuation) anchors the NEW
 * transceiver before the screen's ontrack fires.  Idempotent and race-safe:
 * skips transceivers already anchored and never overwrites an existing entry.
 * Returns how many anchors it added (DIAG only — no behavior change).
 */
export function _anchorTransceiverMetaFromMidMap(sessionId: string): number {
  if (!state._pc) return 0
  let anchored = 0
  for (const [mid, meta] of _remoteMidToTrackName) {
    if (meta.sessionId !== sessionId) continue
    const tx = state._pc.getTransceivers().find((t) => t.mid === mid)
    if (tx && !_transceiverMeta.has(tx)) {
      _transceiverMeta.set(tx, meta)
      anchored += 1
    }
  }
  return anchored
}
/** Display-friendly TrackType → the publisher's NATIVE track names currently
 *  known for the local streams.  Populated by startCall (mic/camera) and
 *  shareStream (screen); consumed by ``_updatePublishedTracks`` so the room
 *  registry + presence carry the REAL active track set when the camera is
 *  toggled off/on or the screen is stopped (F2). */
export const _localTrackNamesByDisplay = new Map<TrackType, string[]>()

/** Sessions this caller has subscribed to (registry/prune bookkeeping). */
export const _subscribedSessions = new Set<string>()

export const HEARTBEAT_INTERVAL_MS = 20_000 // must be < the 60 s registry TTL
