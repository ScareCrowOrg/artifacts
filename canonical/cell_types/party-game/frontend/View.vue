<template>
  <div class="party-game bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <div class="cell-header mb-3 flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
          {{ $t('partyGame.title') || 'Party Game' }}
        </h3>
        <p v-if="localRoomId" class="text-xs text-text-secondary dark:text-text-secondary-dark leading-tight">
          {{ localRoomId }}
        </p>
      </div>
      <span
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full"
        :class="stateConnected
          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
          : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'"
      >
        <span class="w-1.5 h-1.5 rounded-full" :class="stateConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'" />
        {{ stateConnected ? ($t('partyGame.live') || 'Live') : ($t('partyGame.offline') || 'Offline') }}
      </span>
    </div>

    <!-- ── Room join (no room pinned yet) ─────────────────────────────────── -->
    <div v-if="!localRoomId" class="flex flex-col items-center justify-center py-8 text-text-secondary dark:text-text-secondary-dark">
      <label class="text-xs font-medium w-full max-w-xs text-left" for="party-game-room">{{ $t('partyGame.roomPlaceholder') || 'Room name…' }}</label>
      <input
        id="party-game-room"
        v-model="roomInput"
        type="text"
        class="mt-1 w-full max-w-xs px-3 py-2 text-sm rounded-lg border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary/40"
        :placeholder="$t('partyGame.roomPlaceholder') || 'Room name…'"
        :maxlength="256"
        @keyup.enter="handleJoinRoom"
      />
      <button
        class="mt-3 px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!roomInput.trim()"
        @click="handleJoinRoom"
      >
        {{ $t('partyGame.joinRoom') || 'Join' }}
      </button>
    </div>

    <!-- ── In-room content ────────────────────────────────────────────────── -->
    <template v-else>
      <!-- LOBBY -->
      <div v-if="isLobby" class="space-y-4">
        <p class="text-sm font-medium text-text-primary dark:text-text-primary-dark">{{ $t('partyGame.lobbyTitle') || 'Waiting for players' }}</p>
        <p class="text-xs text-text-secondary dark:text-text-secondary-dark">{{ $t('partyGame.lobbyHint') || 'Share this room name so friends can join.' }}</p>
        <div>
          <p class="text-xs font-semibold mb-1">{{ $t('partyGame.players') || 'Players' }} ({{ partyStore.participants.length }})</p>
          <ul v-if="partyStore.participants.length" class="space-y-1">
            <li v-for="p in partyStore.participants" :key="p.sessionId ?? p.participantId" class="flex items-center justify-between text-sm">
              <span class="text-text-primary dark:text-text-primary-dark">{{ p.displayName }}</span>
              <span v-if="p.participantId === myParticipantId" class="text-xs opacity-70">{{ $t('partyGame.you') || 'You' }}</span>
            </li>
          </ul>
          <p v-else class="text-xs opacity-70">{{ $t('partyGame.noPlayers') || 'No players yet' }}</p>
        </div>
        <button
          class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="partyStore.participants.length < 2"
          @click="handleStartGame"
        >
          {{ $t('partyGame.startGame') || 'Start Game' }}
        </button>
      </div>

      <!-- GAME -->
      <div v-else-if="game" class="space-y-3">
        <!-- Round banner -->
        <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span class="font-semibold text-text-primary dark:text-text-primary-dark">
            {{ $t('partyGame.round') || 'Round' }} {{ game.round }} {{ $t('partyGame.of') || 'of' }} {{ game.totalRounds }}
          </span>
          <span v-if="game.phase !== 'finished'" class="text-text-secondary dark:text-text-secondary-dark">
            {{ game.drawerName }} · {{ $t('partyGame.drawerLabel') || 'Drawing' }}
            <span v-if="game.category">· {{ $t('partyGame.category') || 'Category' }}: {{ game.category }}</span>
          </span>
          <span v-if="game.hintCount > 0" class="text-xs text-primary dark:text-primary-light">
            {{ $t('partyGame.hint') || 'Hint' }} x{{ game.hintCount }}
          </span>
        </div>

        <!-- Secret word (drawer only) -->
        <div
          v-if="isDrawer && mySecretWord"
          class="px-3 py-2 rounded border border-primary/30 bg-primary/5 text-sm font-semibold text-primary dark:text-primary-light"
        >
          {{ $t('partyGame.yourWord') || 'Your word' }}: {{ mySecretWord }}
        </div>

        <!-- Canvas -->
        <div class="rounded-lg overflow-hidden border border-border dark:border-border-dark bg-black relative">
          <canvas
            ref="canvasEl"
            width="800"
            height="500"
            class="block w-full touch-none"
            :class="isDrawer ? 'cursor-crosshair' : 'cursor-default'"
            @pointerdown="isDrawer ? handlePointerDown($event) : undefined"
            @pointermove="isDrawer ? handlePointerMove($event) : undefined"
            @pointerup="isDrawer ? handlePointerUp($event) : undefined"
            @pointerleave="handlePointerLeave"
          />
          <p v-if="!isDrawer" class="absolute bottom-1 left-1 text-xs text-white/70 bg-black/50 px-1.5 py-0.5 rounded">
            {{ $t('partyGame.youAreGuesser') || 'Watch the drawing and guess the word!' }}
          </p>
        </div>

        <!-- Toolbar (drawer only) -->
        <div v-if="isDrawer && game.phase !== 'finished'" class="flex flex-wrap items-center gap-2">
          <span
            v-for="c in COLOR_PALETTE"
            :key="c"
            class="w-6 h-6 rounded-full border border-white/40 cursor-pointer"
            :style="{ backgroundColor: c }"
            :class="activeColor === c ? 'ring-2 ring-primary' : ''"
            @click="activeColor = c"
          />
          <span
            v-for="w in STROKE_WIDTHS"
            :key="w"
            class="h-6 px-1.5 flex items-center justify-center rounded border cursor-pointer text-[10px]"
            :class="activeWidth === w ? 'bg-primary text-white' : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary'"
            @click="activeWidth = w"
          >
            {{ w }}
          </span>
          <button
            class="px-2 py-1 text-xs rounded border"
            :class="activeTool === 'pen' ? 'bg-primary text-white' : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary'"
            @click="activeTool = 'pen'"
          >
            {{ $t('partyGame.toolPen') || 'Pen' }}
          </button>
          <button
            class="px-2 py-1 text-xs rounded border"
            :class="activeTool === 'eraser' ? 'bg-primary text-white' : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary'"
            @click="toggleEraser"
          >
            {{ $t('partyGame.toolEraser') || 'Eraser' }}
          </button>
          <button
            class="px-2 py-1 text-xs rounded border bg-surface-light dark:bg-surface-dark-light text-text-secondary hover:bg-surface-hover"
            @click="handleClearCanvas"
          >
            {{ $t('partyGame.clear') || 'Clear' }}
          </button>
          <p class="text-xs text-text-secondary dark:text-text-secondary-dark">{{ $t('partyGame.youAreDrawer') || 'You are the drawer — draw the word!' }}</p>
        </div>

        <!-- Guess feed -->
        <div class="border border-border dark:border-border-dark rounded-lg p-3 space-y-2">
          <div class="feed-list h-32 overflow-y-auto space-y-1">
            <p v-if="gameStore.guesses.length === 0" class="text-xs text-text-secondary dark:text-text-secondary-dark">{{ $t('partyGame.guessingDisabled') || 'The game has not started yet.' }}</p>
            <div
              v-for="msg in gameStore.guesses"
              :key="msg.id"
              class="text-sm leading-snug"
              :class="{
                'font-semibold text-primary dark:text-primary-light': msg.type === 'system',
                'text-amber-600 dark:text-amber-400': msg.type === 'hint',
                'text-green-600 dark:text-green-400': msg.isCorrect,
              }"
            >
              <span v-if="msg.type !== 'system'" class="font-semibold text-text-primary dark:text-text-primary-dark">{{ msg.displayName }}:</span>
              <span class="break-words">{{ msg.text }}</span>
            </div>
          </div>
          <div class="flex gap-2">
            <input
              v-model="draftGuess"
              type="text"
              class="flex-1 px-3 py-2 text-sm rounded-lg border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
              :placeholder="$t('partyGame.guessWordPlaceholder') || 'Guess the word…'"
              :disabled="!canGuess"
              @keyup.enter="handleSubmitGuess"
            />
            <button
              class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!canGuess || !draftGuess.trim()"
              @click="handleSubmitGuess"
            >
              {{ $t('partyGame.send') || 'Send' }}
            </button>
          </div>
          <p v-if="guessError" class="text-xs text-error dark:text-error-light">{{ guessError }}</p>
        </div>

        <!-- Scoreboard -->
        <div class="border border-border dark:border-border-dark rounded-lg p-3">
          <h4 class="text-sm font-semibold mb-2 text-text-primary dark:text-text-primary-dark">{{ $t('partyGame.scoreboard') || 'Scoreboard' }}</h4>
          <ul class="space-y-1 text-sm">
            <li v-for="s in sortedScores" :key="s.participantId" class="flex items-center justify-between">
              <span class="text-text-primary dark:text-text-primary-dark">{{ s.displayName }}</span>
              <span class="font-semibold">{{ s.score }}</span>
            </li>
          </ul>
          <p v-if="game.phase === 'finished'" class="mt-2 text-sm font-semibold text-primary dark:text-primary-light">
            {{ $t('partyGame.gameOver') || 'Game Over' }} — {{ $t('partyGame.winner') || 'Winner' }}: {{ winnerName }}
          </p>
        </div>

        <!-- Round controls (drawer) -->
        <div v-if="isDrawer && game.phase !== 'finished'" class="flex gap-2">
          <button class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition" @click="handleNextRound">
            {{ $t('partyGame.nextRound') || 'Next Round' }}
          </button>
          <button class="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition" @click="handleEndGame">
            {{ $t('partyGame.endGame') || 'End Game' }}
          </button>
        </div>
      </div>

      <!-- Leave -->
      <button
        class="mt-3 px-3 py-1.5 text-xs rounded border border-border dark:border-border-dark text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition"
        @click="handleLeaveRoom"
      >
        {{ $t('partyGame.leaveRoom') || 'Leave' }}
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * @file PartyGame View.vue
 * @description Drawing / guessing party game UI (Gartic-like with AI).
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Layer 1 (Hydration): resolve roomId from props on mount
 * - Layer 2 (Buffer Local): local refs for UI state (room, word, tool, strokes)
 * - Layer 3 (Persistence): every write goes through the backend action
 *   (join/start/guess/stroke), never by mutating the distributed branches.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  useGameStore,
  useGameRealtime,
  type GamePhase,
  type GameState,
  type GuessMessage,
  type Stroke,
  type Point2D,
} from './gameStore'
import { usePartyStore } from '#artifacts/shared/stores/partyStore'
import { PartyGameCell } from './PartyGameCell'
import {
  commitStroke,
  createStroke,
  eventToCanvasPoint,
  extendStroke,
  renderStrokes,
  renderStroke,
} from './canvas'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:party-game')
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

// ── Store + realtime ────────────────────────────────────────────────────────
const gameStore = useGameStore()
const partyStore = usePartyStore()
const { stateConnected } = useGameRealtime()
const cell = new PartyGameCell()

// ── Constants ────────────────────────────────────────────────────────────────
const COLOR_PALETTE = ['#000000', '#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ffffff']
const STROKE_WIDTHS = [2, 4, 8]

// ── Buffer Local (Layer 2) ──────────────────────────────────────────────────
const roomInput = ref('')
const localRoomId = ref<string>(resolveRoomId())
const mySessionId = ref<string>(generateSessionId())
const myParticipantId = ref<string>('')
const mySecretWord = ref<string>('')
const draftGuess = ref('')
const guessError = ref<string | null>(null)
const activeTool = ref<'pen' | 'eraser'>('pen')
const activeColor = ref('#000000')
const activeWidth = ref(4)
const inProgressStroke = ref<Stroke | null>(null)
const canvasEl = ref<HTMLCanvasElement | null>(null)

function resolveRoomId(): string {
  const direct = props.roomId
  const fromCell = props.cell?.initial_data?.roomId ?? props.cell?.data?.roomId
  const value = direct ?? fromCell ?? ''
  return typeof value === 'string' ? value.trim() : ''
}

function generateSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `pg-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

// ── Computed ────────────────────────────────────────────────────────────────
const game = computed(() => gameStore.game)
const isLobby = computed(() => !game.value || game.value.phase === 'lobby')
const isDrawer = computed(() => Boolean(game.value && myParticipantId.value && game.value.drawerId === myParticipantId.value))
const canGuess = computed(() => {
  if (!game.value || !localRoomId.value) return false
  if (isDrawer.value) return false
  return ['draw', 'guess', 'reveal'].includes(game.value.phase)
})

const sortedScores = computed(() => {
  const players = game.value?.players ?? []
  const scores = game.value?.scores ?? {}
  return [...players]
    .map((p) => ({ participantId: p.participantId, displayName: p.displayName, score: scores[p.participantId] ?? 0 }))
    .sort((a, b) => b.score - a.score)
})

const winnerName = computed(() => {
  const top = sortedScores.value[0]
  return top && top.score > 0 ? top.displayName : '—'
})

// ── Canvas helpers ──────────────────────────────────────────────────────────
function canvasCtx(): CanvasRenderingContext2D | null {
  return canvasEl.value?.getContext('2d') ?? null
}

function renderCanvas(): void {
  const ctx = canvasCtx()
  const el = canvasEl.value
  if (!ctx || !el) return
  renderStrokes(ctx, gameStore.strokes, el.width, el.height)
  if (inProgressStroke.value && inProgressStroke.value.points.length > 1) {
    renderStroke(ctx, inProgressStroke.value)
  }
}

// Redraw when committed strokes arrive (remote or own echo) and when the
// in-progress stroke is confirmed (id present in the store) → drop the buffer.
watch(
  () => gameStore.strokes.length,
  () => {
    const pending = inProgressStroke.value
    if (pending?.id && gameStore.strokes.some((s) => s.id === pending.id)) {
      inProgressStroke.value = null
    }
    renderCanvas()
  },
)

// ── Pointer handlers (drawer) ───────────────────────────────────────────────
function handlePointerDown(event: PointerEvent): void {
  if (!isDrawer.value || !canvasEl.value) return
  event.preventDefault()
  canvasEl.value.setPointerCapture(event.pointerId)
  inProgressStroke.value = createStroke(activeTool.value, activeColor.value, activeWidth.value, eventToCanvasPoint(canvasEl.value, event))
}

function handlePointerMove(event: PointerEvent): void {
  if (!isDrawer.value || !inProgressStroke.value || !canvasEl.value) return
  extendStroke(canvasCtx() as CanvasRenderingContext2D, inProgressStroke.value, eventToCanvasPoint(canvasEl.value, event))
}

async function handlePointerUp(event: PointerEvent): Promise<void> {
  if (!isDrawer.value || !inProgressStroke.value || !canvasEl.value) return
  canvasEl.value.releasePointerCapture(event.pointerId)
  const stroke = commitStroke(inProgressStroke.value)
  // Keep the buffer until the store confirms the stroke (no flicker); the
  // watcher above clears it once the id appears in gameStore.strokes.
  await cell.appendStroke(localRoomId.value, stroke)
}

function handlePointerLeave(): void {
  // Nothing to do: the in-progress stroke is committed on pointerup only.
}

function toggleEraser(): void {
  activeTool.value = activeTool.value === 'eraser' ? 'pen' : 'eraser'
  activeColor.value = activeTool.value === 'eraser' ? '#000000' : activeColor.value
}

async function handleClearCanvas(): Promise<void> {
  if (!isDrawer.value) return
  inProgressStroke.value = null
  await cell.clearCanvas(localRoomId.value)
}

// ── Actions ─────────────────────────────────────────────────────────────────
async function handleJoinRoom(): Promise<void> {
  const name = roomInput.value.trim()
  if (!name) return
  localRoomId.value = name
  roomInput.value = ''
  await joinAndHydrate(name)
}

async function joinAndHydrate(roomId: string): Promise<void> {
  partyStore.currentRoom = roomId
  try {
    const join = await cell.joinGame(roomId, mySessionId.value)
    if (join.success && join.output.participantId) {
      myParticipantId.value = String(join.output.participantId)
    }
  } catch (err) {
    logger.warn('[joinAndHydrate] join failed', err)
  }
  // Hydrate from the snapshot RESPONSE BODY — the WSS router is forward-only,
  // so a WS snapshot_request on connect is never answered; if the WS was not
  // yet connected when the backend published, the store would stay blank
  // until the next action.  The HTTP body is the reliable hydration path.
  const snap = await cell.requestSnapshot(roomId).catch(() => null)
  if (snap?.success && snap.output) {
    const out = snap.output as {
      state?: GameState
      strokes?: Stroke[]
      guesses?: GuessMessage[]
      secretWord?: string
    }
    if (out.state) gameStore.game = out.state
    if (out.strokes) gameStore.strokes = out.strokes
    if (out.guesses) gameStore.guesses = out.guesses
    if (out.secretWord && isDrawer.value) mySecretWord.value = out.secretWord
  }
}

async function handleStartGame(): Promise<void> {
  await cell.startGame(localRoomId.value)
}

async function handleNextRound(): Promise<void> {
  mySecretWord.value = ''
  await cell.nextRound(localRoomId.value)
}

async function handleEndGame(): Promise<void> {
  await cell.endGame(localRoomId.value)
}

async function handleSubmitGuess(): Promise<void> {
  const text = draftGuess.value.trim()
  if (!text || !canGuess.value) return
  guessError.value = null
  const result = await cell.submitGuess(localRoomId.value, text)
  if (result.success) {
    draftGuess.value = ''
  } else {
    guessError.value = result.error ?? null
  }
}

async function handleLeaveRoom(): Promise<void> {
  await cell.leaveGame(localRoomId.value, mySessionId.value).catch(() => undefined)
  partyStore.currentRoom = null
  gameStore.reset()
  myParticipantId.value = ''
  mySecretWord.value = ''
  localRoomId.value = ''
}

// ── Secret word fetch (drawer only) ─────────────────────────────────────────
watch(
  () => [game.value?.round, game.value?.phase, game.value?.drawerId],
  async () => {
    if (game.value && game.value.phase !== 'finished') {
      if (isDrawer.value && !mySecretWord.value && ['draw', 'guess', 'reveal'].includes(game.value.phase)) {
        const res = await cell.getSecret(localRoomId.value)
        if (res.success && res.output.secretWord) {
          mySecretWord.value = String(res.output.secretWord)
        }
      } else if (!isDrawer.value) {
        mySecretWord.value = ''
      }
    }
  },
)

// ── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(() => {
  logger.info('[party-game] mounted', { roomId: localRoomId.value })
  if (localRoomId.value) {
    void joinAndHydrate(localRoomId.value)
  }
})

onUnmounted(() => {
  if (localRoomId.value) {
    void cell.leaveGame(localRoomId.value, mySessionId.value).catch(() => undefined)
  }
})
</script>

<style scoped>
.party-game {
  font-family: 'Inter', sans-serif;
}

.feed-list {
  scrollbar-width: thin;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
