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
        <div v-else class="flex items-center gap-3">
          <!-- Connection indicator -->
          <span
            v-if="partyConnected"
            class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            {{ $t('planetHall.live') }}
          </span>
          <!-- Party button -->
          <button
            class="ph-btn text-sm px-3 py-1.5"
            :disabled="partyStarting || isProvisioning"
            @click="togglePartyCall"
          >
            <span v-if="partyConnected">{{ $t('planetHall.leaveCall') }}</span>
            <span v-else-if="isProvisioning">{{ $t('planetHall.provisioning') }}</span>
            <span v-else-if="partyStarting">{{ $t('planetHall.connecting') }}</span>
            <span v-else>{{ $t('planetHall.startCall') }}</span>
          </button>
          <!-- Party connection error -->
          <span
            v-if="partyConnectionError"
            class="text-xs text-red-600 dark:text-red-400 max-w-[200px] truncate"
            :title="partyConnectionError"
            role="alert"
          >
            {{ partyConnectionError }}
          </span>
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
        <p class="text-sm ph-text-muted">
          {{ $t('planetHall.loading') }}
        </p>
      </div>

      <!-- Error banner -->
      <div
        v-if="errorMessage"
        class="ph-fade-in ph-error-banner mb-6"
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
          <p class="ph-text-secondary" style="margin-bottom: 0.75rem;">
            {{ $t('planetHall.notAuthenticated') }}
          </p>
          <a
            href="/"
            class="ph-btn"
          >
            {{ $t('planetHall.loginButton') }}
          </a>
        </div>

        <!-- Messages section (using messages-cell) -->
        <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-1 mb-8 p-6">
          <h2 class="ph-card-header mb-4">
            {{ $t('planetHall.messages') }}
          </h2>
          <MessagesCellView ref="messagesCellRef" />
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
              <label class="block text-sm mb-1 ph-label">
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
              <label class="block text-sm mb-1 ph-label">
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

        <!-- Requests section (auth required, using requests-cell) -->
        <template v-if="isAuthenticated">
          <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-2 mb-8 p-6">
            <h2 class="ph-card-header mb-4">
              {{ $t('planetHall.requests') }}
            </h2>
            <RequestsCellView />
          </section>

          <!-- Create request form -->
          <section class="ph-card ph-fade-in-up ph-fade-in-up--delay-2 p-6">
            <h2 class="ph-card-header mb-4">
              {{ $t('planetHall.createRequest') }}
            </h2>

            <form @submit.prevent="handleCreateRequest" class="space-y-4">
              <div>
                <label class="block text-sm mb-1 ph-label">
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
              <!-- Viewer grid for access requests -->
              <div v-if="newRequest.request_type === 'access' && viewersBuffer.length > 0">
                <label class="block text-sm mb-2 ph-label">
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
              <!-- Allowance request fields or when no viewers loaded -->
              <div v-else>
                <div class="mb-3">
                  <label class="block text-sm mb-1 ph-label">
                    Artifact ID (optional)
                  </label>
                  <input
                    v-model="newRequest.artifact_id"
                    type="text"
                    placeholder="e.g. mesh-cell"
                    class="ph-input"
                  />
                  <!-- Allowance status indicator -->
                  <div
                    v-if="allowanceStatus === 'allowed'"
                    class="mt-2 text-xs ph-status--allowed"
                  >
                    ✅ Você já possui acesso a este artifact
                  </div>
                  <div
                    v-else-if="allowanceStatus === 'pending'"
                    class="mt-2 text-xs ph-status--pending"
                  >
                    ⏳ Solicitação já enviada, aguardando resposta
                  </div>
                </div>
                <label class="block text-sm mb-1 ph-label">
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
                  :disabled="requestSending || !!allowanceStatus || allowanceLoading"
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
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBaseViewer } from '@/composables/useBaseViewer'
import { useThemeSync } from '#artifacts/shared/composables/useThemeSync'
import { useLocaleSync } from '#artifacts/shared/composables/useLocaleSync'
import { createLogger } from '@/utils/logger'
import MessagesCellView from '#canonical/cell_types/messages-cell/frontend/View.vue'
import RequestsCellView from '#canonical/cell_types/requests-cell/frontend/View.vue'
import { useRequestsCell } from '#canonical/cell_types/requests-cell/frontend/composables/useRequestsCell'
import { usePartyCalls } from '#artifacts/shared/composables/usePartyCalls'
import './planet-hall.css'
import en from './i18n/en.json'
import pt from './i18n/pt.json'

const log = createLogger('planet:hall')

const { t } = useI18n()

// ── Party Calls Integration ──
const { isConnected: partyConnected, isProvisioning, startCall, hangUp: partyHangUp, connectionError: partyConnectionError } = usePartyCalls()

const partyStarting = ref(false)

function togglePartyCall(): void {
  if (partyConnected.value) {
    partyHangUp()
  } else {
    partyConnectionError.value = null
    partyStarting.value = true
    startCall('planet-lobby').catch((err) => {
      partyConnectionError.value = err instanceof Error ? err.message : String(err)
    }).finally(() => {
      partyStarting.value = false
      // Clear transient error after 10 s so user doesn't stare at stale
      // "failed to start" after already having hung up.
      setTimeout(() => { partyConnectionError.value = null }, 10_000)
    })
  }
}

const {
  loadingState, errorMessage, isAuthenticated,
  apiFetch, formatDate,
  loadData, mergeCellI18n,
} = useBaseViewer({
  i18n: {
    messages: [
      { locale: 'en', messages: en },
      { locale: 'pt', messages: pt },
    ],
  },
})

// Theme and locale synchronization with Cockpit-Vue
useThemeSync()
useLocaleSync()

// ── Shared reactive state from requests-cell for allowance awareness ─────
const requestsApi = useRequestsCell()

// ── Buffer Locals (REACTIVITY_ISOLATION.md) ──────────────────────────────
const viewersBuffer = ref<any[]>([])
const planetOwnerId = ref('')
const allowedArtifactIds = ref<Set<string>>(new Set())
const allowanceLoading = ref(false)

const messageSending = ref(false)
const requestSending = ref(false)

const newMessage = reactive({
  subject: '',
  body: '',
})

const newRequest = reactive({
  request_type: 'allowance',
  message: '',
  artifact_id: '',
})

const messagesCellRef = ref<any>(null)

const selectedViewerId = ref('')

// ── Computed: Allowance Status ──────────────────────────────────────────
const allowanceStatus = computed<'allowed' | 'pending' | null>(() => {
  const aid = newRequest.artifact_id?.trim()
  if (!aid || newRequest.request_type !== 'allowance') return null
  if (allowedArtifactIds.value.has(aid)) return 'allowed'
  const hasPending = requestsApi.requests.value.some(
    (r: any) =>
      r.status === 'pending'
      && r.request_type === 'allowance'
      && r.payload?.artifact_id === aid
  )
  if (hasPending) return 'pending'
  return null
})

watch(() => newRequest.request_type, () => {
  selectedViewerId.value = ''
})

// ── Data Loading ─────────────────────────────────────────────────────────

async function loadPlanetInfo() {
  try {
    const data: any = await apiFetch('/api/v1/auth/planet-info')
    planetOwnerId.value = data.planet_owner_id || ''
  } catch (err) {
    log.warn('[loadPlanetInfo] failed', err)
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

async function loadAllowances() {
  allowanceLoading.value = true
  try {
    const data: any = await apiFetch('/api/inbox/allowances')
    const ids = Array.isArray(data?.artifact_ids) ? data.artifact_ids : []
    allowedArtifactIds.value = new Set(ids)
  } catch (err) {
    log.warn('[loadAllowances] failed', err)
    allowedArtifactIds.value = new Set()
  } finally {
    allowanceLoading.value = false
  }
}

async function loadViewerData() {
  const tasks = [loadPlanetInfo(), loadViewers(), loadAllowances()]
  if (isAuthenticated.value) {
    // Load requests via the shared composable (kept in sync with
    // RequestsCellView — no separate requestsBuffer needed)
    tasks.push(requestsApi.loadRequests())
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
    // Refresh messages cell to show the new message
    messagesCellRef.value?.loadData()
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
      body.payload = {}
      if (newRequest.artifact_id) {
        body.payload.artifact_id = newRequest.artifact_id
      }
      body.message = newRequest.message
    }
    await apiFetch('/api/inbox/requests', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    // ── Reactive state sync (Buffer Local Pattern) ──
    // Inject pending artifact into local buffer immediately so UI updates
    // without waiting for server round-trip.
    //
    // Note: Intentionally sparse shape for allowanceStatus computed consumption.
    // Only fields read by allowanceStatus are included (status, request_type,
    // payload.artifact_id). If a future computed or template needs _id,
    // sender_id, created_at, etc., hydrate from the server response or expand
    // this injection point.
    if (body.request_type === 'allowance' && body.payload?.artifact_id) {
      requestsApi.injectLocalRequest({
        status: 'pending',
        request_type: 'allowance',
        payload: { artifact_id: body.payload.artifact_id },
      })
    }
    newRequest.request_type = 'allowance'
    newRequest.message = ''
    newRequest.artifact_id = ''
    selectedViewerId.value = ''
    // Background refresh requests via shared composable
    requestsApi.loadRequests()
  } catch (err) {
    log.warn('[handleCreateRequest] failed', err)
  } finally {
    requestSending.value = false
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────

onMounted(() => {
  // Pre-load cell translations to validate mergeCellI18n integration.
  // Fire-and-forget: cells also call loadCellI18n in their own onMounted,
  // but this starts loading earlier and validates the composable wiring.
  mergeCellI18n('messages-cell')
  mergeCellI18n('requests-cell')
  loadData(loadViewerData)
})
</script>
