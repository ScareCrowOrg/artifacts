<template>
  <div class="party-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 shadow-sm">
    <div class="cell-header mb-3 flex items-center justify-between">
      <h3 class="text-lg font-semibold text-primary dark:text-primary-light">
        {{ $t('partyCell.title') }}
      </h3>
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
        <!-- Provisioning banner -->
        <div
          v-if="isProvisioning"
          class="provisioning-banner flex items-center gap-2 mb-4 px-4 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800 text-sm"
        >
          <span class="spinner inline-block h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          {{ $t('partyCell.provisioningMessage') }}
        </div>

        <template v-if="!isProvisioning">
          <svg class="h-12 w-12 mb-3 opacity-40" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <p class="text-sm mb-4">{{ $t('partyCell.notConnected') }}</p>
          <button
            class="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isProvisioning"
            @click="handleStartCall"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
            </svg>
            {{ $t('partyCell.startCall') }}
          </button>
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
            :key="idx"
            class="remote-video relative bg-black rounded overflow-hidden aspect-video"
          >
            <video
              :ref="(el) => attachRemoteVideo(idx, el as HTMLVideoElement | null)"
              autoplay
              playsinline
              class="w-full h-full object-cover"
            />
            <span class="absolute bottom-1 left-1 text-xs text-white bg-black/50 px-1.5 py-0.5 rounded">
              {{ localParticipants[idx]?.displayName || $t('partyCell.remoteUser') }}
            </span>
          </div>
        </div>

        <!-- No remote participants placeholder -->
        <div
          v-else
          class="flex items-center justify-center py-6 text-text-secondary dark:text-text-secondary-dark text-sm border border-dashed border-border dark:border-border-dark rounded"
        >
          {{ $t('partyCell.waitingForOthers') }}
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

          <!-- Share screen -->
          <button
            class="control-btn px-3 py-2 text-sm bg-surface-light dark:bg-surface-dark-light text-text-secondary dark:text-text-secondary-dark rounded-lg hover:bg-surface-hover dark:hover:bg-surface-dark-hover transition flex items-center gap-1.5"
            :title="$t('partyCell.shareScreen')"
            @click="handleShareScreen"
          >
            <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" />
            </svg>
            <span class="text-xs">{{ $t('partyCell.shareScreen') }}</span>
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
import { usePartyCalls } from '#artifacts/shared/composables/usePartyCalls'
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
  isProvisioning,
  localStream,
  remoteStreams,
  participants,
  connectionError,
  startCall,
  shareStream,
  muteAudio,
  hangUp,
} = usePartyCalls()

// ── Buffer Local (Layer 2): Local refs for UI state ──
const localIsConnected = ref(false)
const localConnectionError = ref<string | null>(null)
const localIsMuted = ref(false)

// Sync buffer locals with composable state
watch(isConnected, (val) => {
  localIsConnected.value = val
})

watch(connectionError, (val) => {
  localConnectionError.value = val
})

// ── Computed ──

/** Convert remoteStreams Map to a flat array for v-for rendering */
const remoteStreamList = computed(() => {
  return Array.from(remoteStreams.value.entries())
})

/** Local participants list from the distributed store */
const localParticipants = computed(() => {
  return participants.value || []
})

// ── Video element attachment ──

/** Map to hold references to remote video elements by index */
const remoteVideoElements = new Map<number, HTMLVideoElement>()

function attachRemoteVideo(idx: number, el: HTMLVideoElement | null): void {
  if (el) {
    remoteVideoElements.set(idx, el)
    const stream = remoteStreamList.value[idx]?.[1]
    if (stream && el.srcObject !== stream) {
      el.srcObject = stream
    }
  }
}

// ── Actions ──

async function handleStartCall(): Promise<void> {
  const roomId = props.roomId || 'default-room'
  logger.info('[handleStartCall] Starting call in room:', roomId)
  await startCall(roomId)
}

function handleMuteToggle(): void {
  muteAudio()
  localIsMuted.value = !localIsMuted.value
}

async function handleShareScreen(): Promise<void> {
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: true,
      audio: true,
    })
    await shareStream(stream)
  } catch (err: any) {
    logger.warn('[handleShareScreen] Failed or cancelled:', err?.message)
  }
}

function handleHangUp(): void {
  hangUp()
  localIsConnected.value = false
  localConnectionError.value = null
}

function handleRetry(): void {
  localConnectionError.value = null
  handleStartCall()
}

// ── Lifecycle ──
onMounted(() => {
  logger.info('Party Cell mounted', { roomId: props.roomId })

  // Auto-start call if roomId is provided
  if (props.roomId) {
    handleStartCall()
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
