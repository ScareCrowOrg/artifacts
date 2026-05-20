<template>
  <div class="planet-hall min-h-screen flex flex-col">
    <!-- Starfield background -->
    <div class="starfield" aria-hidden="true"></div>
    <div class="nebula-orb nebula-orb--purple" aria-hidden="true"></div>
    <div class="nebula-orb nebula-orb--cyan" aria-hidden="true"></div>
    <div class="nebula-orb nebula-orb--accent" aria-hidden="true"></div>

    <!-- Header -->
    <header class="ph-header w-full">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 class="ph-header-title">
          {{ $t('planetHall.title') }}
        </h1>
        <div v-if="!isAuthenticated" class="text-sm">
          <a
            href="/"
            class="ph-login-link"
          >
            {{ $t('planetHall.loginButton') }}
          </a>
        </div>
      </div>
    </header>

    <main class="flex-1 w-full max-w-4xl mx-auto px-4 py-6">
      <!-- Hero -->
      <section class="ph-hero ph-fade-in">
        <div class="ph-hero-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: #c084fc;">
            <circle cx="12" cy="12" r="10"/>
            <circle cx="12" cy="12" r="4"/>
            <line x1="12" y1="2" x2="12" y2="6"/>
            <line x1="12" y1="18" x2="12" y2="22"/>
            <line x1="2" y1="12" x2="6" y2="12"/>
            <line x1="18" y1="12" x2="22" y2="12"/>
          </svg>
        </div>
        <h1 class="ph-hero-title">{{ $t('planetHall.title') }}</h1>
        <p class="ph-hero-subtitle">{{ $t('planetHall.subtitle') }}</p>
      </section>

      <!-- Loading -->
      <div v-if="loadingState" class="ph-fade-in text-center py-12">
        <p class="text-sm" style="color: rgba(255, 255, 255, 0.4);">
          {{ $t('planetHall.loading') }}
        </p>
      </div>

      <!-- Error banner -->
      <div
        v-if="errorMessage"
        class="ph-fade-in mb-6 px-4 py-3 rounded-lg"
        style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #f87171; font-size: 0.875rem;"
        role="alert"
      >
        {{ errorMessage }}
      </div>

      <template v-if="!loadingState">
        <!-- Guest notice -->
        <div
          v-if="!isAuthenticated"
          class="ph-guest-notice ph-fade-in-up ph-fade-in-up--delay-1 mb-8"
        >
          <p style="color: rgba(255, 255, 255, 0.5); margin-bottom: 0.75rem;">
            {{ $t('planetHall.notAuthenticated') }}
          </p>
          <a
            href="/"
            class="ph-btn"
          >
            {{ $t('planetHall.loginButton') }}
          </a>
        </div>

        <!-- Messages section -->
        <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-1 mb-8 p-6">
          <h2 class="ph-card-header mb-4">
            {{ $t('planetHall.messages') }}
          </h2>

          <div
            v-if="messagesBuffer.length === 0"
            class="ph-empty"
          >
            {{ $t('planetHall.noMessages') }}
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="msg in messagesBuffer"
              :key="msg._id || msg.id"
              class="ph-card-message p-4"
            >
              <div class="flex items-start justify-between gap-2">
                <div>
                  <h3 class="font-semibold" style="color: rgba(255, 255, 255, 0.85);">
                    {{ msg.payload?.subject || $t('planetHall.noSubject') }}
                  </h3>
                  <p class="text-sm mt-1" style="color: rgba(255, 255, 255, 0.45);">
                    {{ msg.payload?.body || '' }}
                  </p>
                </div>
                <span
                  v-if="msg.created_at"
                  class="text-xs shrink-0"
                  style="color: rgba(255, 255, 255, 0.3);"
                >
                  {{ formatDate(msg.created_at) }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <!-- Create message form (auth required) -->
        <section
          v-if="isAuthenticated"
          class="ph-card ph-fade-in-up ph-fade-in-up--delay-2 mb-8 p-6"
        >
          <h2 class="ph-card-header mb-4">
            {{ $t('planetHall.sendMessage') }}
          </h2>

          <form @submit.prevent="handleCreateMessage" class="space-y-4">
            <div>
              <label class="block text-sm mb-1" style="color: rgba(255, 255, 255, 0.5);">
                {{ $t('planetHall.subject') }}
              </label>
              <input
                v-model="newMessage.subject"
                type="text"
                required
                class="ph-input"
              />
            </div>
            <div>
              <label class="block text-sm mb-1" style="color: rgba(255, 255, 255, 0.5);">
                {{ $t('planetHall.body') }}
              </label>
              <textarea
                v-model="newMessage.body"
                rows="3"
                required
                class="ph-input"
              ></textarea>
            </div>
            <div class="flex justify-end">
              <button
                type="submit"
                :disabled="messageSending"
                class="ph-btn"
              >
                {{ messageSending ? $t('planetHall.sending') : $t('planetHall.send') }}
              </button>
            </div>
          </form>
        </section>

        <!-- Requests section (auth required) -->
        <template v-if="isAuthenticated">
          <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-2 mb-8 p-6">
            <h2 class="ph-card-header mb-4">
              {{ $t('planetHall.requests') }}
            </h2>

            <div
              v-if="requestsBuffer.length === 0"
              class="ph-empty"
            >
              {{ $t('planetHall.noRequests') }}
            </div>

            <div v-else class="space-y-3">
              <div
                v-for="req in requestsBuffer"
                :key="req._id || req.id"
                class="ph-card-message p-4"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <h3 class="font-semibold" style="color: rgba(255, 255, 255, 0.85);">
                      {{ req.request_type || $t('planetHall.unknownRequest') }}
                    </h3>
                    <p class="text-sm mt-1" style="color: rgba(255, 255, 255, 0.45);">
                      {{ req.payload?.message || '' }}
                    </p>
                  </div>
                  <div class="text-right shrink-0">
                    <span
                      class="ph-badge"
                      :class="statusBadgeClass(req.status)"
                    >
                      {{ req.status }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Create request form -->
          <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-2 p-6">
            <h2 class="ph-card-header mb-4">
              {{ $t('planetHall.createRequest') }}
            </h2>

            <form @submit.prevent="handleCreateRequest" class="space-y-4">
              <div>
                <label class="block text-sm mb-1" style="color: rgba(255, 255, 255, 0.5);">
                  {{ $t('planetHall.requestType') }}
                </label>
                <select
                  v-model="newRequest.request_type"
                  required
                  class="ph-input"
                >
                  <option value="allowance">{{ $t('planetHall.allowance') }}</option>
                  <option value="access">{{ $t('planetHall.access') }}</option>
                </select>
              </div>
              <!-- Viewer grid for access requests (FIXED: swapped) -->
              <div v-if="newRequest.request_type === 'access' && viewersBuffer.length > 0">
                <label class="block text-sm mb-2" style="color: rgba(255, 255, 255, 0.5);">
                  {{ $t('planetHall.selectViewer') }}
                </label>
                <div class="viewer-grid">
                  <button
                    v-for="viewer in viewersBuffer"
                    :key="viewer.id"
                    type="button"
                    :class="['viewer-card', { 'viewer-card--selected': selectedViewerId === viewer.id }]"
                    :disabled="viewer.has_allowance"
                    @click="selectedViewerId = viewer.id"
                  >
                    <span class="viewer-card__name">{{ viewer.name || viewer.id }}</span>
                    <span
                      v-if="viewer.has_allowance"
                      class="viewer-card__badge"
                    >{{ $t('planetHall.viewerGranted') }}</span>
                  </button>
                </div>
              </div>
              <!-- Textarea for allowance requests or when no viewers loaded -->
              <div v-else>
                <label class="block text-sm mb-1" style="color: rgba(255, 255, 255, 0.5);">
                  {{ $t('planetHall.message') }}
                </label>
                <textarea
                  v-model="newRequest.message"
                  rows="3"
                  required
                  class="ph-input"
                ></textarea>
              </div>
              <div class="flex justify-end">
                <button
                  type="submit"
                  :disabled="requestSending"
                  class="ph-btn"
                >
                  {{ requestSending ? $t('planetHall.sending') : $t('planetHall.submit') }}
                </button>
              </div>
            </form>
          </section>
        </template>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBaseViewer } from '@/composables/useBaseViewer'
import { createLogger } from '@/utils/logger'
import './planet-hall.css'

const log = createLogger('planet:hall')

const { t } = useI18n()

const {
  loadingState, errorMessage, isAuthenticated,
  apiFetch, formatDate,
  loadData,
} = useBaseViewer()

// ── Buffer Locals (REACTIVITY_ISOLATION.md) ──────────────────────────────
const messagesBuffer = ref<any[]>([])
const requestsBuffer = ref<any[]>([])
const viewersBuffer = ref<any[]>([])
const planetOwnerId = ref('')

const messageSending = ref(false)
const requestSending = ref(false)

const newMessage = reactive({
  subject: '',
  body: '',
})

const newRequest = reactive({
  request_type: 'allowance',
  message: '',
})

const selectedViewerId = ref('')

watch(() => newRequest.request_type, () => {
  selectedViewerId.value = ''
})

// ── Helpers ──────────────────────────────────────────────────────────────

function statusBadgeClass(status?: string) {
  switch (status) {
    case 'pending':   return 'ph-badge--pending'
    case 'approved':  return 'ph-badge--approved'
    case 'rejected':  return 'ph-badge--rejected'
    default:          return 'ph-badge--default'
  }
}

// ── Data Loading ─────────────────────────────────────────────────────────

async function loadPlanetInfo() {
  try {
    const data: any = await apiFetch('/api/v1/auth/planet-info')
    planetOwnerId.value = data.planet_owner_id || ''
  } catch (err) {
    log.warn('[loadPlanetInfo] failed', err)
  }
}

async function loadMessages() {
  try {
    const data: any = await apiFetch('/api/inbox/messages')
    messagesBuffer.value = Array.isArray(data) ? data : []
  } catch (err) {
    log.warn('[loadMessages] failed', err)
    messagesBuffer.value = []
  }
}

async function loadRequests() {
  try {
    const data: any = await apiFetch('/api/inbox/requests')
    requestsBuffer.value = Array.isArray(data) ? data : []
  } catch (err) {
    log.warn('[loadRequests] failed', err)
    requestsBuffer.value = []
  }
}

async function loadViewers() {
  try {
    const data: any = await apiFetch('/api/viewers')
    viewersBuffer.value = Array.isArray(data) ? data : []
  } catch (err) {
    log.warn('[loadViewers] failed', err)
    viewersBuffer.value = []
  }
}

async function loadViewerData() {
  // Handshake is handled internally by useBaseViewer.loadData
  // Always load planet info (public endpoint)
  // Always load viewers (public endpoint)
  // Only load messages/requests if authenticated via handshake
  const tasks = [loadPlanetInfo(), loadViewers()]
  if (isAuthenticated.value) {
    tasks.push(loadMessages(), loadRequests())
  }

  await Promise.all(tasks)
}

// ── Actions ──────────────────────────────────────────────────────────────

async function handleCreateMessage() {
  if (!newMessage.subject || !newMessage.body) {
    errorMessage.value = 'Please fill in both subject and message.'
    return
  }
  if (!planetOwnerId.value) {
    errorMessage.value = 'Planet owner information not available. Please try again.'
    return
  }
  messageSending.value = true
  errorMessage.value = ''
  try {
    await apiFetch('/api/inbox/messages', {
      method: 'POST',
      body: JSON.stringify({
        target_user_id: planetOwnerId.value,
        subject: newMessage.subject,
        body: newMessage.body,
      }),
    })
    newMessage.subject = ''
    newMessage.body = ''
    await loadMessages()
  } catch (err) {
    log.warn('[handleCreateMessage] failed', err)
  } finally {
    messageSending.value = false
  }
}

async function handleCreateRequest() {
  if (newRequest.request_type === 'access') {
    if (!selectedViewerId.value) {
      errorMessage.value = 'Please select a viewer to request access for.'
      return
    }
  } else if (!newRequest.message) {
    errorMessage.value = 'Please fill in a message describing your artifact allowance request.'
    return
  }
  if (!planetOwnerId.value) {
    errorMessage.value = 'Planet owner information not available. Please try again.'
    return
  }
  requestSending.value = true
  errorMessage.value = ''
  try {
    const selectedViewer = viewersBuffer.value.find(
      (v: any) => v.id === selectedViewerId.value
    )
    const viewerName = selectedViewer?.name || selectedViewerId.value
    const body: Record<string, any> = {
      target_user_id: planetOwnerId.value,
      request_type: newRequest.request_type,
    }
    if (newRequest.request_type === 'access') {
      body.payload = {
        viewer_id: selectedViewerId.value,
        viewer_name: viewerName,
      }
      body.message = `Requesting access for viewer: ${viewerName}`
    } else {
      body.message = newRequest.message
    }
    await apiFetch('/api/inbox/requests', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    newRequest.request_type = 'allowance'
    newRequest.message = ''
    selectedViewerId.value = ''
    await loadRequests()
  } catch (err) {
    log.warn('[handleCreateRequest] failed', err)
  } finally {
    requestSending.value = false
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────

onMounted(() => {
  loadData(loadViewerData)
})
</script>
