<template>
  <div class="party-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-3 flex items-center justify-between">
      <div>
        <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
          {{ $t('partyCell.title') }}
        </h3>
        <!-- F3 / INC-6: show the named session once connected -->
        <p
          v-if="localIsConnected && localSessionName"
          class="text-xs text-text-secondary dark:text-text-secondary-dark leading-tight"
        >
          {{ localSessionName }}
        </p>
      </div>
      <!-- Connection indicator -->
      <span
        v-if="localIsConnected"
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        {{ $t('partyCell.live') }}
      </span>
      <span
        v-else-if="localConnectionError"
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-red-500" />
        {{ $t('partyCell.error') }}
      </span>
      <span
        v-else
        class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-gray-400" />
        {{ $t('partyCell.offline') }}
      </span>
    </div>

    <div class="cell-content space-y-4">
      <!-- ERROR STATE -->
      <div
        v-if="localConnectionError"
        class="error-state p-3 bg-error-light dark:bg-error-dark text-error-dark dark:text-error-light rounded border border-error text-sm"
        role="alert"
      >
        <p>{{ localConnectionError }}</p>
        <button
          class="mt-2 px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition"
          @click="handleRetry"
        >
          {{ $t('partyCell.retry') }}
        </button>
      </div>

      <!-- DISCONNECTED STATE (no call active) -->
      <div
        v-if="!localIsConnected && !localConnectionError"
        class="flex flex-col items-center justify-center py-8 text-text-secondary dark:text-text-secondary-dark"
      >
        <!-- Connecting spinner (F1): visible from provisioning through registering,
             with a phase-specific message — no more silent gap between provision
             and ICE connect, and the "live" badge only lights up when ready. -->
        <div
          v-if="isConnecting"
          class="connecting-banner flex items-center gap-2 mb-4 px-4 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800 text-sm"
        >
          <span class="spinner inline-block h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          {{ phaseStatusMessage }}
        </div>

        <template v-if="!isConnecting">
          <svg class="h-12 w-12 mb-3 opacity-40" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <p class="text-sm mb-4">{{ $t('partyCell.notConnected') }}</p>

          <!-- F3 / INC-6: session name input → roomId (fallback 'default-room') -->
          <div class="flex flex-col items-center gap-2 mb-4 w-full max-w-xs">
            <label
              class="text-xs font-medium text-text-secondary dark:text-text-secondary-dark w-full text-left"
              for="party-session-name"
            >
              {{ $t('partyCell.startWithName') }}
            </label>
            <input
              id="party-session-name"
              v-model="sessionName"
              type="text"
              class="w-full px-3 py-2 text-sm rounded-lg border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary/40"
              :placeholder="$t('partyCell.sessionNamePlaceholder')"
              :maxlength="256"
              @keyup.enter="handleStartCall"
            />
          </div>

          <button
            class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isConnecting"
            @click="handleStartCall"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
            </svg>
            {{ $t('partyCell.startCall') }}
          </button>

          <!-- F4: available sessions (only when no roomId is pinned) -->
          <div v-if="!props.roomId" class="sessions-section mt-6 w-full max-w-sm">
            <p class="text-xs font-medium mb-2 text-text-primary dark:text-text-primary-dark">
              {{ $t('partyCell.availableSessions') }}
            </p>
            <div
              v-if="localAvailableRooms.length === 0"
              class="text-xs opacity-70 px-3 py-2 border border-dashed border-border dark:border-border-dark rounded"
            >
              {{ $t('partyCell.noSessions') }}
            </div>
            <ul v-else class="space-y-2">
              <li
                v-for="room in localAvailableRooms"
                :key="room.roomId"
                class="flex items-center justify-between gap-2 px-3 py-2 bg-surface-light dark:bg-surface-dark-light rounded border border-border dark:border-border-dark"
              >
                <span class="text-sm truncate">{{ roomNameLabel(room) }}</span>
                <span class="text-xs opacity-70 shrink-0">{{ room.sessionCount }}</span>
                <button
                  class="px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition shrink-0"
                  @click="handleJoinRoom(room.roomId)"
                >
                  {{ $t('partyCell.joinSession') }}
                </button>
              </li>
            </ul>
          </div>
        </template>
      </div>

      <!-- CONNECTED STATE -->
      <template v-if="localIsConnected">
        <!-- Remote participants video grid -->
        <div
          v-if="remoteStreamList.length > 0"
          class="video-grid grid gap-2"
          :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(180px, 1fr))` }"
        >
          <div
            v-for="(remote, idx) in remoteStreamList"
            :key="remote.key"
            class="remote-video relative bg-black rounded overflow-hidden aspect-video"
            :class="remote.isScreen ? 'screen-tile border-2 border-primary' : ''"
          >
            <video
              :ref="(el) => attachRemoteVideo(remote.key, el as HTMLVideoElement | null)"
              autoplay
              playsinline
              class="w-full h-full object-cover"
            />
            <svg
              v-if="remote.isScreen"
              class="absolute top-1 left-1 h-4 w-4 text-white bg-black/50 rounded p-0.5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
            </svg>
            <span class="absolute bottom-1 left-1 text-xs text-white bg-black/50 px-1.5 py-0.5 rounded">
              {{ remoteLabel(remote) }}
            </span>
            <!-- F6: maximize this tile (Fullscreen API, falls back to grid expand) -->
            <button
              class="absolute top-1 right-1 h-6 w-6 flex items-center justify-center text-white bg-black/50 rounded hover:bg-black/70 transition"
              :title="$t('partyCell.maximize')"
              @click="toggleFullscreen(remote.key)"
            >
              <svg class="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
              </svg>
            </button>
          </div>
        </div>

        <!-- No remote participants placeholder -->
        <div
          v-else
          class="flex items-center justify-center py-6 text-text-secondary dark:text-text-secondary-dark text-sm border border-dashed border-border dark:border-border-dark rounded"
        >
          {{ $t('partyCell.waitingForOthers') }}
        </div>

        <!-- F2: active screen-share indicator -->
        <div
          v-if="localIsSharingScreen"
          class="flex items-center justify-center gap-1.5 text-xs text-primary dark:text-primary-light font-medium"
        >
          <span class="w-2 h-2 rounded-full bg-primary animate-pulse" />
          {{ $t('partyCell.youAreSharing') }}
        </div>

        <!-- Controls -->
        <div class="controls-section flex flex-wrap items-center justify-center gap-2 pt-3 border-t border-border dark:border-border-dark">
          <!-- Mute toggle -->
          <button
            class="control-btn px-3 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
            :class="localIsMuted
              ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
              : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover'"
            :title="$t('partyCell.muteAudio')"
            @click="handleMuteToggle"
          >
            <svg v-if="!localIsMuted" class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
            </svg>
            <svg v-else class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.25 9.75L19.5 12m0 0l2.25 2.25M19.5 12l2.25-2.25M19.5 12l-2.25 2.25m-10.5-6l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" />
            </svg>
            <span class="text-xs">{{ localIsMuted ? $t('partyCell.unmute') : $t('partyCell.mute') }}</span>
          </button>

          <!-- Camera toggle (F2 — independent of mic/screen) -->
          <button
            class="control-btn px-3 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
            :class="localCameraEnabled
              ? 'bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover'
              : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'"
            :title="$t('partyCell.camera')"
            @click="handleCameraToggle"
          >
            <svg v-if="localCameraEnabled" class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
            </svg>
            <svg v-else class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 9.75L3.75 3.75M20.25 20.25l-6-6M14.25 5.25a4.5 4.5 0 015.625 5.625M9.75 14.25a4.5 4.5 0 015.625 5.625" />
            </svg>
            <span class="text-xs">{{ localCameraEnabled ? $t('partyCell.camera') : $t('partyCell.cameraOff') }}</span>
          </button>

          <!-- Screen share toggle (F2 — start / stop) -->
          <button
            class="control-btn px-3 py-2 text-sm rounded-lg transition flex items-center gap-1.5"
            :class="localIsSharingScreen
              ? 'bg-primary text-white'
              : 'bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark hover:bg-surface-hover dark:hover:bg-surface-dark-hover'"
            :title="localIsSharingScreen ? $t('partyCell.stopSharing') : $t('partyCell.shareScreen')"
            @click="handleScreenShare"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
            </svg>
            <span class="text-xs">{{ localIsSharingScreen ? $t('partyCell.stopSharing') : $t('partyCell.shareScreen') }}</span>
          </button>

          <!-- Refresh presence + discovery (F5) -->
          <button
            class="control-btn px-3 py-2 text-sm bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark rounded-lg hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
            :title="$t('partyCell.refresh')"
            @click="handleRefresh"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            <span class="text-xs">{{ $t('partyCell.refresh') }}</span>
          </button>

          <!-- Hang up -->
          <button
            class="control-btn px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition flex items-center gap-1.5"
            :title="$t('partyCell.hangUp')"
            @click="handleHangUp"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.712 4.33a9.027 9.027 0 011.652 1.306c.51.51.944 1.064 1.306 1.652M16.712 4.33l-3.448 4.138m3.448-4.138a9.014 9.014 0 00-9.424 0M19.5 19.5l-15-15m0 0l4.138 3.448M4.5 4.5L.75.75m4.138 4.138A9.015 9.015 0 002.25 12c0 2.362.876 4.522 2.33 6.158M4.5 4.5l2.33 6.158m0 0L3 18.75m3.83-10.092a6.75 6.75 0 019.34 9.34" />
            </svg>
            <span class="text-xs">{{ $t('partyCell.hangUp') }}</span>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * @file PartyCell View.vue
 * @description View component for Party Cell — video grid, call controls, connection indicator.
 *
 * Buffer Local Pattern (REACTIVITY_ISOLATION.md):
 * - Layer 1 (Hydration): Read from props on mount/init
 * - Layer 2 (Buffer Local): local refs for UI state
 * - Layer 3 (Persistence): Sync via cell actions on explicit user action
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePartyCalls, type AvailableRoom } from '#artifacts/shared/composables/usePartyCalls'
import type { Participant } from '#artifacts/shared/stores/partyStore'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:party-cell')

const { t } = useI18n()

// ── Props ──
interface Props {
  roomId?: string
}

const props = withDefaults(defineProps<Props>(), {
  roomId: undefined,
})

// ── PartyCalls Composable ──
const {
  isConnected,
  connectionPhase,
  isConnecting,
  cameraEnabled,
  isSharingScreen,
  localStream,
  remoteStreams,
  participants,
  connectionError,
  startCall,
  muteAudio,
  toggleCamera,
  toggleScreenShare,
  refreshRoom,
  listAvailableRooms,
  joinRoom,
  hangUp,
} = usePartyCalls()

// ── Buffer Local (Layer 2): Local refs for UI state ──
const localIsConnected = ref(false)
const localConnectionError = ref<string | null>(null)
const localIsMuted = ref(false)
const localCameraEnabled = ref(false)
const localIsSharingScreen = ref(false)
/** F3: session name the user typed (fallback 'default-room'). */
const sessionName = ref(props.roomId ?? '')
/** The roomId actually in use (shown in the header when connected). */
const localSessionName = ref('')
/** F4: active sessions discovered on mount (only when no roomId). */
const localAvailableRooms = ref<AvailableRoom[]>([])

// Sync buffer locals with composable state
watch(isConnected, (val) => {
  localIsConnected.value = val
})

watch(connectionError, (val) => {
  localConnectionError.value = val
})

watch(cameraEnabled, (val) => {
  localCameraEnabled.value = val
})

watch(isSharingScreen, (val) => {
  localIsSharingScreen.value = val
})

/** F1: phase-specific connecting message (spinner + text). */
const phaseStatusMessage = computed(() => {
  switch (connectionPhase.value) {
    case 'provisioning':
      return t('partyCell.provisioningMessage')
    case 'requesting-media':
      return t('partyCell.requestingMedia')
    case 'signaling':
      return t('partyCell.signaling')
    case 'registering':
      return t('partyCell.registering')
    default:
      return t('partyCell.connecting')
  }
})

// ── Computed ──

/**
 * Convert remoteStreams Map to a flat array for v-for rendering, matching each
 * stream to its participant by sessionId so the video-grid label shows the
 * correct display name (partyStore.Participant.sessionId).
 *
 * Screen-share tiles are keyed ``{sessionId}/screen`` (see _handleRemoteTrack):
 * they resolve the owning participant by stripping the suffix and are flagged
 * ``isScreen`` so the grid renders a dedicated highlighted tile.
 */
interface RemoteGridEntry {
  /** The remoteStreams Map key (sessionId or `${sessionId}/screen`). */
  key: string
  stream: MediaStream
  participant?: Participant
  /** Whether this tile is a screen share (separate from the camera tile). */
  isScreen: boolean
}

const remoteStreamList = computed<RemoteGridEntry[]>(() => {
  const parts = participants.value || []
  return Array.from(remoteStreams.value.entries()).map(([key, stream]) => {
    const isScreen = key.endsWith('/screen')
    const ownerId = isScreen ? key.slice(0, -'/screen'.length) : key
    return {
      key,
      stream,
      isScreen,
      participant: parts.find((p) => p.sessionId === ownerId),
    }
  })
})

/** Tile label: owner name for camera tiles, owner + "screen share" for screen. */
function remoteLabel(remote: RemoteGridEntry): string {
  const name = remote.participant?.displayName
  if (remote.isScreen) {
    return name ? `${name} · ${t('partyCell.screenShare')}` : t('partyCell.screenShare')
  }
  return name || t('partyCell.remoteUser')
}

/** Local participants list from the distributed store */
const localParticipants = computed(() => {
  return participants.value || []
})

// ── Video element attachment ──

/** Map to hold references to remote video elements by remote key (sessionId or
 *  ``{sessionId}/screen`` — the stable v-for ``:key``), so a removed tile can
 *  drop its own entry (Finding C: the old idx-keyed map never cleaned up, so
 *  toggleFullscreen could target a detached element after a reorder). */
const remoteVideoElements = new Map<string, HTMLVideoElement>()

function attachRemoteVideo(key: string, el: HTMLVideoElement | null): void {
  if (el) {
    remoteVideoElements.set(key, el)
    const stream = remoteStreamList.value.find((r) => r.key === key)?.stream
    if (stream && el.srcObject !== stream) {
      el.srcObject = stream
    }
  } else {
    // Vue calls the ref with null on tile unmount/removal — clean the stale entry.
    remoteVideoElements.delete(key)
  }
}

// ── Actions ──

/** Sanitize a session name into a valid roomId (main.py regex
 *  ``^[\w:._-]{1,256}$``) — empty input falls back to 'default-room' (INC-6). */
function sanitizeRoomId(name: string): string {
  const cleaned = name.trim().replace(/[^\w:._-]/g, '-').slice(0, 256)
  return cleaned || 'default-room'
}

async function handleStartCall(): Promise<void> {
  const roomId = sanitizeRoomId(sessionName.value || props.roomId || '')
  localSessionName.value = roomId
  logger.info('[handleStartCall] Starting call in room:', roomId)
  await startCall(roomId)
}

function handleMuteToggle(): void {
  muteAudio()
  localIsMuted.value = !localIsMuted.value
}

function handleCameraToggle(): void {
  toggleCamera()
}

function handleScreenShare(): void {
  void toggleScreenShare()
}

async function handleRefresh(): Promise<void> {
  await refreshRoom()
  // When not pinned to a room, also refresh the available-sessions list
  if (!props.roomId) await loadAvailableRooms()
}

async function handleJoinRoom(roomId: string): Promise<void> {
  localSessionName.value = roomId
  await joinRoom(roomId)
}

/** Label for a discovered room: prefer the first participant's display name,
 *  fall back to the roomId (edge case: active room without a displayName). */
function roomNameLabel(room: AvailableRoom): string {
  const first = room.sessions?.[0]
  return first?.displayName || room.roomId
}

async function loadAvailableRooms(): Promise<void> {
  try {
    localAvailableRooms.value = await listAvailableRooms()
  } catch (err) {
    logger.warn('[loadAvailableRooms] failed:', err instanceof Error ? err.message : err)
    localAvailableRooms.value = []
  }
}

function handleHangUp(): void {
  hangUp()
  localIsConnected.value = false
  localConnectionError.value = null
  localSessionName.value = ''
}

function handleRetry(): void {
  localConnectionError.value = null
  void handleStartCall()
}

/** F6: maximize a video tile — Fullscreen API, falling back to expanding the
 *  tile across the grid when the API is absent OR the browser's permissions
 *  policy rejects ``requestFullscreen`` (e.g. the planet iframe's ``allow``
 *  list).  B1 factor 2: the old ``return`` after ``void container
 *  .requestFullscreen()`` swallowed the rejection and never reached the
 *  ``maximized-tile`` fallback. */
async function toggleFullscreen(key: string): Promise<void> {
  const el = remoteVideoElements.get(key)
  const container = el?.parentElement
  if (!container) return
  if (typeof container.requestFullscreen === 'function') {
    if (document.fullscreenElement) {
      void document.exitFullscreen()
      return
    }
    try {
      await container.requestFullscreen()
    } catch (err) {
      // Permissions policy / missing user gesture → the promise rejects.  Fall
      // back to expanding the tile across the grid (B1 fixed).
      container.classList.toggle('maximized-tile')
    }
    return
  }
  // Fallback (no Fullscreen API): expand within the grid
  container.classList.toggle('maximized-tile')
}

// ── Lifecycle ──
onMounted(() => {
  logger.info('Party Cell mounted', { roomId: props.roomId })

  // Auto-start call if roomId is provided; otherwise discover active sessions
  if (props.roomId) {
    localSessionName.value = props.roomId
    void handleStartCall()
  } else {
    void loadAvailableRooms()
  }
})

onUnmounted(() => {
  // Clean up remote video element references
  remoteVideoElements.clear()
  logger.info('Party Cell unmounted')
})
</script>

<style scoped>
.party-cell {
  font-family: 'Inter', sans-serif;
}

.video-grid {
  width: 100%;
}

/* Shared screen tiles span two grid columns so the screen is the focus of the
   grid (GAP 4 — a distinct highlighted tile, not the camera "winning"). */
.screen-tile {
  grid-column: span 2;
}

/* F6 fallback (no Fullscreen API): expanding a tile across the whole grid. */
.maximized-tile {
  grid-column: 1 / -1;
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
