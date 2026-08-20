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
  /** DIAGNOSTIC MIRROR of the most recent screen share (F13 — the ACTIVE
   *  per-instance screen state now lives in ``ctx.screenState`` inside
   *  ``createLocalMediaActions``; this field is written by shareStream/
   *  stopSharing for debug visibility + test backward-compat, never read by
   *  production behavior).  The display stream being shared (screen/3D canvas)
   *  — stopped on hangUp. */
  _screenStream: null as MediaStream | null,
  /** DIAGNOSTIC MIRROR — native MediaStreamTrack id of the most recent shared
   *  screen's DISPLAY AUDIO track (optional — only present when the sharer
   *  checked "share tab audio").  See ``_screenStream`` above. */
  _screenAudioTrackId: null as string | null,
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
  /** True once this PC's ICE ever reached 'connected'/'completed' (set by
   *  ``_waitForIceConnected``).  Lets the 2D/b ICE gate
   *  (``_registerLocalTracksOnSfu``) distinguish a MID-CALL ICE restart (was
   *  connected → short grace then send the offer — the offer completes the
   *  restart) from the INITIAL connection (never connected → wait the full
   *  timeout before a 1st camera/mic opt-in could 425).  Reset on hangUp so a
   *  new call starts fresh. */
  _iceWasEverConnected: false,
  /** DIAGNOSTIC MIRROR — native MediaStreamTrack id of the most recent shared
   *  screen.  The ACTIVE per-instance value lives in ``ctx.screenState.trackId``
   *  (F13); this mirror is written by shareStream/stopSharing for debug +
   *  test backward-compat, never read by production behavior. */
  _screenTrackId: null as string | null,
  /** DIAGNOSTIC MIRROR — the sendonly screen VIDEO transceiver orphaned by the
   *  last stopSharing (``sender.track`` nulled by ``removeTrack`` but the
   *  transceiver kept).  The ACTIVE per-instance orphan lives in
   *  ``ctx.screenState.orphanVideoTx`` (F13) — this mirror is written for debug
   *  visibility + test backward-compat, never read by production behavior.
   *  Reused by the next shareStream via ``replaceTrack`` so each share/stop
   *  cycle does NOT stack a new transceiver (A1; avoids the SFU's 413
   *  accumulation error).  Captured explicitly because the old direction-only
   *  orphan search missed the transceiver once the last offer had re-negotiated
   *  its direction. */
  _orphanScreenTx: null as RTCRtpTransceiver | null,
  /** DIAGNOSTIC MIRROR — the sendonly screen AUDIO transceiver orphaned by the
   *  last stopSharing (Ajuste 1 — display-audio track).  The ACTIVE per-instance
   *  orphan lives in ``ctx.screenState.orphanAudioTx`` (F13).  Reused by the
   *  next shareStream with audio so each share/stop cycle does NOT stack a new
   *  audio transceiver. */
  _orphanScreenAudioTx: null as RTCRtpTransceiver | null,
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
 * stream.id and was pruned.  G1 (bug-hardening): a mid leaves the set when the
 * subscription CONFIRMS (``_subscribedSessions.add`` / PUT /renegotiate in
 * ``_subscribeToRemoteTracks``) — NOT at the ontrack (which fires before the
 * confirm) — or after ``_PENDING_SUBSCRIBE_TIMEOUT_MS`` (guard for a
 * subscription whose confirm never completes — the timeout must never leak
 * protected mids). */
export const _pendingSubscribeMids = new Set<string>()
export const _PENDING_SUBSCRIBE_TIMEOUT_MS = 5000
/**
 * F4 FIX (bug-hardening): mid → timerId for each pending-subscribe timeout.
 * Tracked so ``hangUp``/``onUnmounted`` can cancel them all — a stale timer
 * from a PREVIOUS call must never clear a pending mid re-marked on the NEXT
 * call (would re-introduce the race-H3 drop).  The timer for a mid is also
 * cancelled when the mid is released by ``_unmarkMidPending``.
 */
export const _pendingSubscribeTimers = new Map<string, number>()

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
 *  from concurrent prunes until their subscription CONFIRMS (G1 — release moved
 *  from the ontrack to after _subscribedSessions.add) or the timeout fires.
 *  One bounded 5s timer per mid, cancelled when the mid is released or on
 *  hangUp; a timer firing for an already-cleared mid is a harmless no-op. */
export function _markMidsPending(mids: string[], sessionId: string): void {
  const added: string[] = []
  for (const mid of mids) {
    if (!mid || _pendingSubscribeMids.has(mid)) continue
    _pendingSubscribeMids.add(mid)
    added.push(mid)
    // F4: track the timer id so hangUp/_unmarkMidPending can cancel it.
    const timerId = window.setTimeout(() => {
      _pendingSubscribeMids.delete(mid)
      _pendingSubscribeTimers.delete(mid)
    }, _PENDING_SUBSCRIBE_TIMEOUT_MS)
    _pendingSubscribeTimers.set(mid, timerId)
  }
  if (added.length > 0) {
    log.warn('[pending] marked mids=%j session=%s', added, sessionId)
  }
}

/**
 * G1 FIX (bug-hardening): the subscription for the given mid has CONFIRMED on
 * the SFU (after ``_subscribedSessions.add`` / the PUT /renegotiate round-trip)
 * — the pending protection is released.  This is the ONLY release point; the
 * ontrack no longer releases it (releasing at the ontrack re-opened the race:
 * ``_subscribedSessions.add`` runs after the ontrack, so a stale prune in the
 * ontrack→confirm gap could drop the just-arrived tile).
 */
export function _unmarkMidPending(mid: string | null | undefined, sessionKey: string): void {
  if (mid && _pendingSubscribeMids.delete(mid)) {
    const timerId = _pendingSubscribeTimers.get(mid)
    if (timerId !== undefined) window.clearTimeout(timerId)
    _pendingSubscribeTimers.delete(mid)
    log.warn('[pending] cleared after subscribe confirmed mid=%s session=%s', mid, sessionKey)
  }
}

/** F4 FIX (bug-hardening): cancel every pending-subscribe timeout (hangUp /
 *  onUnmounted) so a stale timer from a previous call can never fire into the
 *  next call's state.  The mids themselves are cleared by the caller (hangUp
 *  already clears ``_pendingSubscribeMids``). */
export function _clearPendingSubscribeTimers(): void {
  for (const timerId of _pendingSubscribeTimers.values()) window.clearTimeout(timerId)
  _pendingSubscribeTimers.clear()
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

/**
 * F13 (review #4/#5 — party-calls-screen-audio-session-isolation): per-instance
 * published screen ids for the SHARED session, keyed by the per-instance
 * `ctx.screenState` object.
 *
 *  - `_updatePublishedTracks` merges the screens of ALL active instances — a
 *    republish from ONE instance (camera/mic toggle, own share stop) must NOT
 *    drop another instance's live screen ids from the registry (that would make
 *    subscribers prune a screen tile that is still flowing on the SFU).
 *  - `hangUp` checks it to decide a SOFT hang-up: if another instance is still
 *    sharing, the shared PC/session/heartbeat/registry must survive (the
 *    glb-content-viewer piggybacks on the party-cell's PC — a hard teardown
 *    would kill the other instance's share).
 *
 * Entries are added on a successful `shareStream`, deleted on `stopSharing`,
 * the share-failure G2 branch, and `hangUp`.
 */
export const _activeScreenIdsByInstance = new Map<object, { videoId: string | null; audioId: string | null }>()

/** Sessions this caller has subscribed to (registry/prune bookkeeping). */
export const _subscribedSessions = new Set<string>()

export const HEARTBEAT_INTERVAL_MS = 20_000 // must be < the 60 s registry TTL

// ─────────────────────────────────────────────────────────────────────────────
// Renegotiation serialization (2C — party-cell-screen-share-sfu-register-fail)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * FIX (party-cell-screen-share-sfu-register-fail, CHANGE_PLAN 2C): serialize
 * renegotiations on the shared peer connection.
 *
 * The diagnosis (H1+H3, `docs/issues/party-cell-screen-share-sfu-register-fail/diagnosis/FINDINGS.md`)
 * proved that when the 2nd participant publishes their screen right after the
 * SFU REUSED the base transceivers to deliver the 1st participant's screen, a
 * renegotiation overlapping another on the SAME PC corrupts the signaling/ICE
 * state — ICE stuck in 'new' (never recovering → `_waitForIceConnected` timeout
 * → the publish was never sent) or, in other environments, an SFU answer the
 * browser rejected at `setRemoteDescription` (`mid='2'`).
 *
 * This promise-chain mutex guarantees only ONE createOffer / setRemoteDescription
 * / answer round-trip runs at a time: the publish offer from `shareStream` and
 * the subscribe offer/answer round-trips queue instead of overlapping.  Each
 * critical section awaits the previous one; a failure in one section never
 * blocks the next (the tail swallows rejections while the caller still receives
 * the original rejection).
 */
let _negotiationTail: Promise<unknown> = Promise.resolve()
export function _withNegotiationLock<T>(fn: () => Promise<T>): Promise<T> {
  const run = _negotiationTail.then(fn, fn)
  _negotiationTail = run.catch(() => {})
  return run
}
