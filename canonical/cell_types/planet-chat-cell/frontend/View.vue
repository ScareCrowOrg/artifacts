<template>
  <div class="planet-chat-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg flex flex-col h-full min-h-[400px]">
    <!-- Header -->
    <div class="cell-header flex items-center justify-between px-4 py-3 border-b border-border dark:border-border-dark">
      <div>
        <h3 class="text-base font-semibold text-primary dark:text-primary-light">
          Planet Chat
        </h3>
        <p class="text-xs text-text-secondary dark:text-text-secondary-dark mt-0.5">
          {{ currentRoomId }}
        </p>
      </div>
      <!-- Connection indicator -->
      <div class="flex items-center gap-2">
        <span
          class="inline-block w-2 h-2 rounded-full"
          :class="isConnected ? 'bg-success' : 'bg-error'"
          :title="isConnected ? 'Connected' : 'Disconnected'"
        />
        <span class="text-xs text-text-secondary dark:text-text-secondary-dark">
          {{ isConnected ? 'Live' : 'Offline' }}
        </span>
      </div>
    </div>

    <!-- Connection error banner -->
    <div
      v-if="connectionError"
      class="px-4 py-2 bg-error-light dark:bg-error-dark text-error-dark dark:text-error-light text-xs"
    >
      {{ connectionError }}
    </div>

    <!-- Room switcher -->
    <div class="room-switch flex gap-2 px-4 py-2 border-b border-border dark:border-border-dark">
      <input
        v-model="roomInput"
        type="text"
        placeholder="Enter room name…"
        class="flex-1 px-2 py-1 text-xs border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-1 focus:ring-primary"
        @keydown.enter.prevent="handleSwitchRoom"
      />
      <button
        :disabled="!roomInput.trim() || roomInput.trim() === currentRoomId"
        class="px-3 py-1 text-xs bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
        @click="handleSwitchRoom"
      >
        Join
      </button>
    </div>

    <!-- Message list -->
    <div
      ref="messageListRef"
      class="messages flex-1 overflow-y-auto px-4 py-3 space-y-2"
    >
      <template v-if="sortedMessages.length === 0 && isHydrated">
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark text-center py-8">
          No messages yet. Start the conversation!
        </p>
      </template>

      <template v-if="sortedMessages.length === 0 && !isHydrated">
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark text-center py-8">
          Loading…
        </p>
      </template>

      <div
        v-for="msg in sortedMessages"
        :key="msg.id"
        class="message-item flex flex-col gap-0.5"
      >
        <div class="flex items-baseline gap-2">
          <span class="text-xs font-semibold text-primary dark:text-primary-light">
            {{ msg.senderId }}
          </span>
          <span class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ formatTimestamp(msg.timestamp) }}
          </span>
        </div>
        <p class="text-sm text-text-primary dark:text-text-primary-dark break-words">
          {{ msg.text }}
        </p>
      </div>
    </div>

    <!-- Typing indicators -->
    <div
      v-if="typingSenders.length > 0"
      class="px-4 py-1 text-xs text-text-secondary dark:text-text-secondary-dark italic"
    >
      {{ typingSenders.join(', ') }} {{ typingSenders.length === 1 ? 'is' : 'are' }} typing…
    </div>

    <!-- Input area -->
    <div class="input-area px-4 py-3 border-t border-border dark:border-border-dark">
      <div class="flex gap-2">
        <input
          v-model="draftMessage"
          type="text"
          placeholder="Type a message…"
          :disabled="isSending || !currentRoomId"
          class="flex-1 px-3 py-2 text-sm border border-border dark:border-border-dark bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark rounded focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
          @keydown.enter.prevent="handleSend"
        />
        <button
          :disabled="!draftMessage.trim() || isSending || !currentRoomId"
          class="px-4 py-2 text-sm bg-primary dark:bg-primary-hover text-white rounded hover:bg-primary-hover transition disabled:opacity-50 disabled:cursor-not-allowed"
          @click="handleSend"
        >
          <span v-if="isSending">…</span>
          <span v-else>Send</span>
        </button>
      </div>
      <p v-if="sendError" class="mt-1 text-xs text-error dark:text-error-light">
        {{ sendError }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { usePlanetChatStore } from './stores/planetChat'
import { useDistributedState } from '@/composables/useDistributedState'
import { usePlanetChat } from './composables/usePlanetChat'
import type { ChatMessage } from './stores/planetChat'

// ─────────────────────────────────────────────────────────────────────────────
// Props — Buffer Local Pattern (REACTIVITY_ISOLATION.md)
// Never mutate props directly; copy to local refs on mount.
// ─────────────────────────────────────────────────────────────────────────────

interface CellObject {
  id?: string
  cellId?: string
  initial_data?: {
    partyId?: string | null
    roomName?: string | null
    maxMessages?: number
  }
  data?: Record<string, unknown>
}

interface Props {
  /** Cell object from DynamicCellView */
  cell?: CellObject
  /** Direct cellId (backward-compatibility) */
  cellId?: string
  /** Direct partyId (backward-compatibility) */
  partyId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  cell: undefined,
  cellId: undefined,
  partyId: null,
})

// ─────────────────────────────────────────────────────────────────────────────
// Buffer Local Pattern — Room resolution
// Priority: explicit partyId prop > initial_data.roomName > initial_data.partyId
// Default: 'global-planet-lobby' (Global Lobby, accessible without parameters)
// ─────────────────────────────────────────────────────────────────────────────

const initialData = computed(() => props.cell?.initial_data ?? props.cell?.data ?? {})

/**
 * Resolve the room identifier from props/initial_data.
 * Falls back to 'global-planet-lobby' so the cell is always usable without
 * explicit configuration.
 */
function resolveRoomId(): string {
  const raw =
    props.partyId ??
    (initialData.value as { roomName?: string | null }).roomName ??
    (initialData.value as { partyId?: string | null }).partyId ??
    null
  return typeof raw === 'string' && raw.trim().length > 0 ? raw.trim() : 'global-planet-lobby'
}

/** The active room name — updated by resolveRoomId() and switchRoom() */
const currentRoomId = ref<string>(resolveRoomId())

/** Full WSS channel identifier aligned with the backend's planet-chat:{roomId} convention */
const channelContextId = computed(() => `planet-chat:${currentRoomId.value}`)

// Keep in sync when props change at runtime
watch(
  () => [props.partyId, props.cell?.initial_data],
  () => {
    const resolved = resolveRoomId()
    if (resolved !== currentRoomId.value) {
      currentRoomId.value = resolved
    }
  },
  { deep: true },
)

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

const chatStore = usePlanetChatStore()

// Initialize store.currentRoom with the resolved value and keep it in sync
// whenever the room changes (either via props update or handleSwitchRoom).
chatStore.currentRoom = currentRoomId.value
watch(currentRoomId, (room) => {
  chatStore.currentRoom = room
})

// ─────────────────────────────────────────────────────────────────────────────
// Distributed state — connect to Redis channel via WSS
// channelContextId is a ComputedRef<string>; useDistributedState accepts it
// and will automatically reconnect when the value changes (room switch).
// ─────────────────────────────────────────────────────────────────────────────

const { isConnected, connectionError } = useDistributedState({
  contextId: channelContextId,
  store: chatStore as unknown as Record<string, unknown>,
  branch: 'messages',
  conflictStrategy: 'append',
})

// ─────────────────────────────────────────────────────────────────────────────
// Chat actions
// usePlanetChat receives the bare roomId (no 'planet-chat:' prefix) because
// the backend main.py adds that prefix internally when publishing to Redis.
// senderId is intentionally omitted so the backend injects the authenticated
// user_id from the session (cells must not import from cockpit-vue stores).
// ─────────────────────────────────────────────────────────────────────────────

const { isSending, sendError, sendMessage, requestSnapshot } = usePlanetChat({
  roomId: currentRoomId,
})

// ─────────────────────────────────────────────────────────────────────────────
// Hydration — request snapshot on mount so existing messages are displayed
// immediately, even if the WSS snapshot_request is not handled server-side.
// ─────────────────────────────────────────────────────────────────────────────

onMounted(async () => {
  // [DEBUG planet-chat B1/B2] Log channel and room context on mount
  console.log('[PlanetChatCell][DEBUG] onMounted — currentRoomId:', currentRoomId.value, 'channelContextId:', channelContextId.value)
  await requestSnapshot()
})

// ─────────────────────────────────────────────────────────────────────────────
// Room switching
// ─────────────────────────────────────────────────────────────────────────────

const roomInput = ref('')

async function handleSwitchRoom() {
  const name = roomInput.value.trim()
  if (!name || name === currentRoomId.value) return

  // Reset local chat state before switching rooms
  chatStore.reset()
  currentRoomId.value = name
  roomInput.value = ''

  // Request the snapshot via HTTP POST for the new room.
  // Note: updating currentRoomId triggers useDistributedState to reconnect
  // (via its watch on resolvedContextId), but the new WebSocket connection
  // is established asynchronously.  The POST snapshot request below is
  // best-effort: if it races ahead of the new WS connection the snapshot
  // message published by the backend will be missed; the WS onopen handler
  // will fire a WebSocket-level snapshot_request shortly after, which the
  // backend will also process.
  await requestSnapshot()
}

// ─────────────────────────────────────────────────────────────────────────────
// Computed views on the store
// ─────────────────────────────────────────────────────────────────────────────

const sortedMessages = computed<ChatMessage[]>(() => chatStore.sortedMessages())

const typingSenders = computed<string[]>(() => chatStore.typingSenders())

const isHydrated = computed(() => chatStore.isHydrated)

// ─────────────────────────────────────────────────────────────────────────────
// Draft input
// ─────────────────────────────────────────────────────────────────────────────

const draftMessage = ref('')

async function handleSend() {
  const text = draftMessage.value.trim()
  if (!text || isSending.value) return

  const ok = await sendMessage(text)
  if (ok) {
    draftMessage.value = ''
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Smart auto-scroll — only scroll to bottom when the user is already at/near
// the bottom, to avoid disrupting manual upward scrolling.
// ─────────────────────────────────────────────────────────────────────────────

const messageListRef = ref<HTMLElement | null>(null)

/** Returns true when the user has not scrolled away from the bottom (within 80px). */
function isNearBottom(): boolean {
  const el = messageListRef.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (messageListRef.value && isNearBottom()) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  },
)

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>
