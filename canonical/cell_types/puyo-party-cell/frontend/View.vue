<template>
  <div class="puyo-party bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <div class="cell-header mb-3 flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
          {{ $t('puyoPartyCell.title') || 'Puyo Party' }}
        </h3>
        <p v-if="localRoomId" class="text-xs text-text-secondary dark:text-text-secondary-dark leading-tight">
          {{ localRoomId }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full"
          :class="gameConnected
            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'"
        >
          <span class="w-1.5 h-1.5 rounded-full" :class="gameConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'" />
          {{ gameConnected ? ($t('puyoPartyCell.live') || 'Live') : ($t('puyoPartyCell.offline') || 'Offline') }}
        </span>
        <button
          v-if="localRoomId"
          class="px-2 py-1 text-xs rounded border border-border dark:border-border-dark text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition"
          @click="handleLeaveRoom"
        >
          {{ $t('puyoPartyCell.leaveRoom') || 'Leave' }}
        </button>
      </div>
    </div>

    <!-- ── Room join (no room pinned yet) ─────────────────────────────────── -->
    <div v-if="!localRoomId" class="flex flex-col items-center justify-center py-8 text-text-secondary dark:text-text-secondary-dark">
      <label class="text-xs font-medium w-full max-w-xs text-left" for="puyo-room">{{ $t('puyoPartyCell.roomPlaceholder') || 'Room name…' }}</label>
      <input
        id="puyo-room"
        v-model="roomInput"
        type="text"
        class="mt-1 w-full max-w-xs px-3 py-2 text-sm rounded-lg border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary/40"
        :placeholder="$t('puyoPartyCell.roomPlaceholder') || 'Room name…'"
        :maxlength="256"
        @keyup.enter="handleJoinRoom"
      />
      <button
        class="mt-3 px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!roomInput.trim()"
        @click="handleJoinRoom"
      >
        {{ $t('puyoPartyCell.joinRoom') || 'Join' }}
      </button>
    </div>

    <!-- ── In-room content ────────────────────────────────────────────────── -->
    <template v-else>
      <!-- LOBBY -->
      <div v-if="isLobby" class="space-y-4">
        <p class="text-sm font-medium text-text-primary dark:text-text-primary-dark">{{ $t('puyoPartyCell.lobbyTitle') || 'Waiting for players' }}</p>
        <p class="text-xs text-text-secondary dark:text-text-secondary-dark">{{ $t('puyoPartyCell.lobbyHint') || 'Share this room name so friends can join.' }}</p>

        <div>
          <p class="text-xs font-semibold mb-1">{{ $t('puyoPartyCell.players') || 'Players' }} ({{ partyStore.participants.length }})</p>
          <ul v-if="partyStore.participants.length" class="space-y-1">
            <li
              v-for="p in partyStore.participants"
              :key="p.sessionId ?? p.participantId"
              class="flex items-center justify-between text-sm"
            >
              <span class="text-text-primary dark:text-text-primary-dark">{{ p.displayName }}</span>
              <span class="inline-flex items-center gap-1 text-xs">
                <span v-if="p.participantId === myParticipantId" class="opacity-70">{{ $t('puyoPartyCell.you') || 'You' }}</span>
                <span
                  class="px-1.5 py-0.5 rounded-full"
                  :class="isPlayerReady(p.participantId)
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'"
                >
                  {{ isPlayerReady(p.participantId) ? ($t('puyoPartyCell.ready') || 'Ready') : ($t('puyoPartyCell.notReady') || 'Not ready') }}
                </span>
              </span>
            </li>
          </ul>
          <p v-else class="text-xs opacity-70">{{ $t('puyoPartyCell.noPlayers') || 'No players yet' }}</p>
        </div>

        <button
          class="px-4 py-2 text-sm rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
          :class="isMeReady
            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
            : 'bg-primary text-white hover:bg-primary-hover'"
          :disabled="isMeReady"
          @click="handleReady"
        >
          {{ $t('puyoPartyCell.ready') || 'Ready' }}
        </button>
        <p v-if="canAutoStart" class="text-xs text-text-secondary dark:text-text-secondary-dark">
          {{ $t('puyoPartyCell.starting') || 'Everyone ready — starting…' }}
        </p>
      </div>

      <!-- GAME -->
      <div v-else-if="game && game.status === 'running'" class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span class="font-semibold text-text-primary dark:text-text-primary-dark">
            {{ $t('puyoPartyCell.round') || 'Round' }} {{ game.round }}
          </span>
          <span class="text-text-secondary dark:text-text-secondary-dark">
            {{ $t('puyoPartyCell.score') || 'Score' }} — {{ localScore }}
          </span>
          <span v-if="myGarbage > 0" class="text-xs text-red-500">
            ⚠ {{ $t('puyoPartyCell.garbage') || 'Garbage' }}: {{ myGarbage }}
          </span>
        </div>

        <div class="flex flex-wrap gap-3">
          <!-- Self board -->
          <div class="board-col">
            <p class="text-xs font-semibold mb-1 text-text-primary dark:text-text-primary-dark">{{ $t('puyoPartyCell.you') || 'You' }}</p>
            <canvas ref="selfCanvas" width="180" height="360" class="board-canvas rounded border border-border dark:border-border-dark" />
          </div>
          <!-- Opponent board -->
          <div class="board-col">
            <p class="text-xs font-semibold mb-1 text-text-primary dark:text-text-primary-dark">
              {{ opponentName || ($t('puyoPartyCell.opponent') || 'Opponent') }} · {{ opponentScore }}
            </p>
            <canvas ref="oppCanvas" width="180" height="360" class="board-canvas rounded border border-border dark:border-border-dark" />
          </div>
        </div>

        <p class="text-xs text-text-secondary dark:text-text-secondary-dark">
          {{ $t('puyoPartyCell.keysHint') || 'Arrows: move · X / Up: rotate · Down: soft drop · Space: hard drop' }}
        </p>

        <!-- Voice (opt-in — Caso B) -->
        <div class="flex items-center gap-2">
          <button
            class="control-btn px-3 py-1.5 text-xs rounded-lg transition flex items-center gap-1.5"
            :class="localMicPublished && !localMicMuted
              ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
              : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover'"
            @click="handleMicToggle"
          >
            {{ micLabel }}
          </button>
        </div>
      </div>

      <!-- GAME OVER -->
      <div v-else-if="game && game.status === 'game_over'" class="space-y-4 text-center py-8">
        <p class="text-lg font-semibold text-text-primary dark:text-text-primary-dark">
          {{ $t('puyoPartyCell.gameOver') || 'Game Over' }}
        </p>
        <p class="text-sm" :class="didIWin ? 'text-green-600 dark:text-green-400' : 'text-text-secondary dark:text-text-secondary-dark'">
          {{ didIWin ? ($t('puyoPartyCell.youWin') || 'You win!') : ($t('puyoPartyCell.youLose') || 'You lose') }}
        </p>
        <p v-if="winnerName" class="text-xs text-text-secondary dark:text-text-secondary-dark">
          {{ $t('puyoPartyCell.winner') || 'Winner' }}: {{ winnerName }}
        </p>
        <button
          class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition"
          @click="handlePlayAgain"
        >
          {{ $t('puyoPartyCell.playAgain') || 'Play Again' }}
        </button>
      </div>

      <!-- Fallback waiting screen (should not normally render) -->
      <div v-else class="py-8 text-center text-sm text-text-secondary dark:text-text-secondary-dark">
        {{ $t('puyoPartyCell.waitingForOpponent') || 'Waiting for the opponent…' }}
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * @file PuyoPartyCell View.vue
 * @description Competitive Puyo Puyo 1v1 (Canvas 2D) — deterministic lockstep
 * engine + server-authoritative sync + opt-in voice.
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Layer 1 (Hydration): resolve roomId from props on mount; hydrate game state
 *   from the snapshot_request HTTP response body (the WSS router is forward-only).
 * - Layer 2 (Buffer Local): local refs for UI/input (room, ready, session, mic).
 * - Layer 3 (Persistence): every write goes through the backend action
 *   (ready / start_game / piece_locked / submit_garbage / game_over), never by
 *   mutating the distributed branch.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePartyCalls } from '#artifacts/shared/composables/usePartyCalls'
import { usePartyStore } from '#artifacts/shared/stores/partyStore'
import { usePuyoStore, usePuyoRealtime, remoteGridOf, type PuyoGameState } from './store/puyoStore'
import { PuyoPartyCell } from './PuyoPartyCell'
import { PuyoSession, parseGrid, createEmptyBoard, type BoardGrid } from './engine/PuyoBoard'
import { calculateGarbage } from './engine/PuyoGarbage'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:puyo-party')
const { t } = useI18n()

// ── Props (Buffer Local Layer 1 — hydrate on mount) ─────────────────────────
interface Props {
  roomId?: string
  cell?: {
    initial_data?: { roomId?: string | null }
    data?: { roomId?: string | null }
  }
}
const props = withDefaults(defineProps<Props>(), { roomId: undefined, cell: undefined })

// ── Stores + realtime ───────────────────────────────────────────────────────
const gameStore = usePuyoStore()
const partyStore = usePartyStore()
const { gameConnected } = usePuyoRealtime()
const cell = new PuyoPartyCell()
const game = computed<PuyoGameState | null>(() => gameStore.game)

// ── PartyCalls (presence + opt-in voice) ────────────────────────────────────
const {
  micEnabled: micPublished,
  muteAudio,
  startCall,
  hangUp,
} = usePartyCalls()

/** Buffer Local (Layer 2): whether the local mic is published (Caso B — the
 *  first mic click ENABLES it).  Synced from the composable via watch. */
const localMicPublished = ref(false)

watch(micPublished, (val) => {
  localMicPublished.value = val
})

// ── Rendering constants ─────────────────────────────────────────────────────
const CELL_COLORS: Record<number, string> = {
  0: '#111827',
  1: '#ef4444',
  2: '#22c55e',
  3: '#3b82f6',
  4: '#facc15',
  5: '#9ca3af',
}

// ── Buffer Local (Layer 2) ──────────────────────────────────────────────────
const roomInput = ref('')
const localRoomId = ref<string>(resolveRoomId())
const myParticipantId = ref<string>(generateParticipantId())
const localScore = ref(0)
const isMeReady = ref(false)
const localMicMuted = ref(false)
const session = ref<PuyoSession | null>(null)
const lastGarbageReceived = ref(0)
const selfCanvas = ref<HTMLCanvasElement | null>(null)
const oppCanvas = ref<HTMLCanvasElement | null>(null)

// Gravity timer + render loop handles
let gravityTimer: ReturnType<typeof setInterval> | null = null
let rafId = 0

function resolveRoomId(): string {
  const direct = props.roomId
  const fromCell = props.cell?.initial_data?.roomId ?? props.cell?.data?.roomId
  const value = direct ?? fromCell ?? ''
  return typeof value === 'string' ? value.trim() : ''
}

function sanitizeRoomId(name: string): string {
  const cleaned = name.trim().replace(/[^\w:._-]/g, '-').slice(0, 256)
  return cleaned || 'default-room'
}

/** Stable per-tab identity for unauthenticated guests (Blocker 5).  Persisted
 *  in sessionStorage so a reload keeps the same id; two tabs get distinct ids
 *  (sessionStorage is per-tab).  For authenticated users the backend resolves
 *  the authoritative ``user_id`` instead (A07 — never trusts this blindly). */
function generateParticipantId(): string {
  const KEY = 'puyo:participantId'
  const fresh = (): string =>
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `puyo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  try {
    const existing = sessionStorage.getItem(KEY)
    if (existing) return existing
    const id = fresh()
    sessionStorage.setItem(KEY, id)
    return id
  } catch {
    return fresh()
  }
}

// ── Computed ────────────────────────────────────────────────────────────────
const isLobby = computed(() => !game.value || game.value.status === 'waiting')

/** The 1v1 match players — from ``game.scores`` (server-authoritative),
 *  NOT from party presence (a spectator or diverging roster order must never
 *  change who the opponent is). */
const matchPlayerIds = computed(() => Object.keys(game.value?.scores ?? {}))

const opponentId = computed(() => {
  const me = myParticipantId.value
  if (!me) return null
  return matchPlayerIds.value.find((id) => id !== me) ?? null
})

const opponentName = computed(() => {
  const id = opponentId.value
  if (!id) return null
  return partyStore.participants.find((p) => p.participantId === id)?.displayName ?? id
})

const opponentScore = computed(() => {
  const id = opponentId.value
  return id ? (game.value?.scores?.[id] ?? 0) : 0
})

const myGarbage = computed(() => {
  const me = myParticipantId.value
  return me ? (game.value?.garbagePending?.[me] ?? 0) : 0
})

const canAutoStart = computed(
  () =>
    isLobby.value &&
    partyStore.participants.length >= 2 &&
    partyStore.participants.every((p) => game.value?.readyFlags?.[p.participantId]),
)

const winnerName = computed(() => {
  const w = game.value?.gameOver?.winnerId
  if (!w) return null
  const winner = partyStore.participants.find((p) => p.participantId === w)
  return winner?.displayName ?? w
})

const didIWin = computed(() => game.value?.gameOver?.winnerId === myParticipantId.value)

const micLabel = computed(() => {
  if (!localMicPublished.value) return t('puyoPartyCell.enableMic') || 'Enable Mic'
  return localMicMuted.value
    ? t('puyoPartyCell.unmute') || 'Unmute'
    : t('puyoPartyCell.mute') || 'Mute'
})

// ── Helpers ─────────────────────────────────────────────────────────────────
function isPlayerReady(pid: string): boolean {
  return Boolean(game.value?.readyFlags?.[pid])
}

function drawBoard(canvas: HTMLCanvasElement | null, board: BoardGrid, piece?: PuyoSession['current'] | null): void {
  const ctx = canvas?.getContext('2d')
  if (!ctx || !canvas) return
  const cellW = canvas.width / 6
  const cellH = canvas.height / 12
  ctx.fillStyle = '#111827'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  for (let y = 0; y < board.length; y++) {
    for (let x = 0; x < board[y].length; x++) {
      const cell = board[y][x]
      if (cell !== 0) {
        ctx.fillStyle = CELL_COLORS[cell] ?? '#9ca3af'
        ctx.fillRect(x * cellW + 1, y * cellH + 1, cellW - 2, cellH - 2)
      }
    }
  }

  if (piece) {
    ctx.fillStyle = CELL_COLORS[piece.a] ?? '#fff'
    ctx.fillRect(piece.x * cellW + 1, piece.y * cellH + 1, cellW - 2, cellH - 2)
    const [dx, dy] = piece.rotation === 0 ? [0, 1] : piece.rotation === 1 ? [1, 0] : piece.rotation === 2 ? [0, -1] : [-1, 0]
    ctx.fillStyle = CELL_COLORS[piece.b] ?? '#fff'
    ctx.fillRect((piece.x + dx) * cellW + 1, (piece.y + dy) * cellH + 1, cellW - 2, cellH - 2)
  }
}

// ── Game session ────────────────────────────────────────────────────────────
function setupGame(seed: number): void {
  if (session.value) return
  logger.info('[puyo] setupGame seed=%d', seed)
  session.value = new PuyoSession(seed)
  // Must-fix (review): do NOT baseline the garbage watcher to the CURRENT
  // pending amount — a player who reconnects mid-match would otherwise absorb
  // (dodge) all garbage accumulated during their absence.  Inject the pending
  // garbage onto the fresh board, THEN baseline so the watcher only injects
  // deltas that arrive afterwards.
  session.value.injectGarbage(myGarbage.value)
  lastGarbageReceived.value = myGarbage.value
  startLoop()
}

function startLoop(): void {
  stopLoop()
  gravityTimer = setInterval(() => onGravityTick(), 800)
  rafId = requestAnimationFrame(renderLoop)
}

function stopLoop(): void {
  if (gravityTimer !== null) {
    clearInterval(gravityTimer)
    gravityTimer = null
  }
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
}

function renderLoop(): void {
  const sess = session.value
  drawBoard(selfCanvas.value, sess ? sess.board : createEmptyBoard(), sess ? sess.current : null)
  const remote = remoteGridOf(game.value, myParticipantId.value)
  drawBoard(oppCanvas.value, remote ? parseGrid(remote) : createEmptyBoard(), null)
  rafId = requestAnimationFrame(renderLoop)
}

function onGravityTick(): void {
  const sess = session.value
  if (!sess || sess.gameOver) return
  if (sess.tick()) afterLock()
}

function afterLock(): void {
  const sess = session.value
  if (!sess || !localRoomId.value) return
  const lock = sess.lastLock
  if (!lock) return
  localScore.value = sess.score

  // Report the locked grid — renders the opponent's board (server-authoritative).
  void cell.lockPiece(localRoomId.value, sess.serializeBoard(), sess.score, myParticipantId.value)

  // A chain ≥2 sends a garbage attack to the opponent (server-arbitrated).
  const amount = calculateGarbage(lock.chains, lock.totalCleared)
  const opp = opponentId.value
  if (amount > 0 && opp) void cell.submitGarbage(localRoomId.value, amount, opp, myParticipantId.value)

  // Board topped out → backend arbitrates the winner.
  if (sess.gameOver) void cell.gameOver(localRoomId.value, 'top-out', myParticipantId.value)
}

// ── Keyboard input ──────────────────────────────────────────────────────────
function onKeyDown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) return
  const sess = session.value
  if (!sess || sess.gameOver || !localRoomId.value) return
  switch (event.key) {
    case 'ArrowLeft':
      event.preventDefault()
      sess.moveLeft()
      break
    case 'ArrowRight':
      event.preventDefault()
      sess.moveRight()
      break
    case 'ArrowUp':
      event.preventDefault()
      sess.rotate(1)
      break
    case 'ArrowDown':
      event.preventDefault()
      if (sess.tick()) afterLock()
      break
    case 'x':
    case 'X':
      sess.rotate(1)
      break
    case 'z':
    case 'Z':
      sess.rotate(-1)
      break
    case ' ':
      event.preventDefault()
      sess.hardDrop()
      afterLock()
      break
  }
}

// ── Watchers ────────────────────────────────────────────────────────────────
// Start/stop the local simulation from the server-authoritative status.
watch(
  () => [game.value?.status, game.value?.seed] as const,
  ([status, seed]) => {
    if (status === 'running' && typeof seed === 'number' && seed !== null) {
      setupGame(seed)
    } else if (status === 'game_over') {
      stopLoop()
      session.value = null
    } else if (status === 'waiting') {
      stopLoop()
      session.value = null
      localScore.value = 0
      isMeReady.value = Boolean(game.value?.readyFlags?.[myParticipantId.value])
    }
  },
)

// Reflect my ready flag from the snapshot.
watch(
  () => game.value?.readyFlags?.[myParticipantId.value],
  (ready) => {
    isMeReady.value = Boolean(ready)
  },
)

// Inject garbage that arrives mid-game into the local session (delta).
watch(
  () => (myParticipantId.value ? (game.value?.garbagePending?.[myParticipantId.value] ?? 0) : 0),
  (pending) => {
    const sess = session.value
    if (!sess || pending <= lastGarbageReceived.value) return
    sess.injectGarbage(pending - lastGarbageReceived.value)
    lastGarbageReceived.value = pending
  },
)

// ── Actions ─────────────────────────────────────────────────────────────────
async function handleJoinRoom(): Promise<void> {
  const name = roomInput.value.trim()
  if (!name) return
  const roomId = sanitizeRoomId(name)
  localRoomId.value = roomId
  roomInput.value = ''
  partyStore.currentRoom = roomId
  await joinRoomAndHydrate(roomId)
}

/** Join the party presence (voice opt-in — Caso B: no mic on join), then
 *  hydrate the game state.  A failed presence (Cloudflare down) does NOT block
 *  the game — the backend roster falls back to readyFlags/participants. */
async function joinRoomAndHydrate(roomId: string): Promise<void> {
  try {
    await startCall(roomId)
  } catch (err: unknown) {
    logger.warn('[puyo] startCall failed', err)
    // A failed startCall internally calls hangUp(), which nulls
    // partyStore.currentRoom and resets the party store — restore it so
    // usePuyoRealtime still connects the game channel (the match must work
    // without Cloudflare presence).
    partyStore.currentRoom = roomId
  }
  await hydrate(roomId)
}

async function hydrate(roomId: string): Promise<void> {
  // The WSS router is forward-only: a WS snapshot_request on connect is never
  // answered and a snapshot published before this client's WS subscribed is
  // lost.  The HTTP response body is the reliable hydration path.
  const snap = await cell.requestSnapshot(roomId, myParticipantId.value).catch(() => null)
  if (snap?.success && snap.output) {
    const out = snap.output as { state?: PuyoGameState; participantId?: string; participants?: Array<{ participantId: string; displayName: string }> }
    // participantId FIRST so the status/seed watcher below sees my id ready.
    if (out.participantId) myParticipantId.value = String(out.participantId)
    if (out.state) {
      gameStore.game = out.state
      isMeReady.value = Boolean(out.state.readyFlags?.[String(out.participantId ?? '')])
    }
    if (Array.isArray(out.participants) && out.participants.length) {
      partyStore.setParticipants(out.participants)
    }
  }
}

async function handleReady(): Promise<void> {
  if (!localRoomId.value) return
  // Pass the local roster as a fallback so the backend can start even if the
  // party presence is not yet populated.
  const participants = partyStore.participants.map((p) => ({ participantId: p.participantId, displayName: p.displayName }))
  const result = await cell.markReady(localRoomId.value, participants, myParticipantId.value)
  if (result.success) {
    isMeReady.value = true
  } else {
    logger.warn('[puyo] ready failed', result.error)
  }
}

async function handlePlayAgain(): Promise<void> {
  if (!localRoomId.value) return
  isMeReady.value = false
  localScore.value = 0
  await cell.startGame(localRoomId.value, myParticipantId.value)
}

async function handleMicToggle(): Promise<void> {
  const wasEnabled = localMicPublished.value
  await muteAudio()
  // Caso B (party-cell-usability-ux): the FIRST click ENABLES the mic
  // (unmuted — the resulting state is false); later clicks flip the mute.
  localMicMuted.value = wasEnabled ? !localMicMuted.value : false
}

async function handleLeaveRoom(): Promise<void> {
  hangUp()
  stopLoop()
  partyStore.currentRoom = null
  gameStore.reset()
  session.value = null
  myParticipantId.value = ''
  isMeReady.value = false
  localRoomId.value = ''
}

// ── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(() => {
  logger.info('[puyo] mounted', { roomId: localRoomId.value })
  window.addEventListener('keydown', onKeyDown)
  if (localRoomId.value) {
    partyStore.currentRoom = localRoomId.value
    void joinRoomAndHydrate(localRoomId.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  stopLoop()
})
</script>

<style scoped>
.puyo-party {
  font-family: 'Inter', sans-serif;
}

.board-canvas {
  display: block;
  width: 100%;
  max-width: 180px;
  image-rendering: pixelated;
}

.control-btn {
  min-width: 80px;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
