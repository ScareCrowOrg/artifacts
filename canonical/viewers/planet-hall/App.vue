<template>
  <div class="planet-hall min-h-screen flex flex-col theme-bg-background">
    <!-- Simplified header -->
    <header class="w-full border-b border-border-light dark:border-border-dark bg-bg-card dark:bg-bg-card-dark">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <h1 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark">
          {{ $t('planetHall.title') }}
        </h1>
        <div v-if="!isAuthenticated" class="text-sm">
          <a
            href="/"
            class="text-primary dark:text-primary-dark hover:opacity-80 transition-opacity"
          >
            {{ $t('planetHall.loginButton') }}
          </a>
        </div>
      </div>
    </header>

    <main class="flex-1 w-full max-w-4xl mx-auto px-4 py-8">
      <!-- Page title -->
      <section class="text-center mb-10">
        <h1 class="text-3xl font-bold text-text-primary dark:text-text-primary-dark mb-2">
          {{ $t('planetHall.title') }}
        </h1>
        <p class="text-text-secondary dark:text-text-secondary-dark">
          {{ $t('planetHall.subtitle') }}
        </p>
      </section>

      <!-- Loading indicators -->
      <div v-if="loadingState" class="text-center py-8">
        <p class="text-text-secondary dark:text-text-secondary-dark">
          {{ $t('planetHall.loading') }}
        </p>
      </div>

      <!-- Error banner -->
      <div
        v-if="errorMessage"
        class="mb-6 p-4 bg-red-900/20 border border-red-700 rounded-lg text-red-300 text-sm"
        role="alert"
      >
        {{ errorMessage }}
      </div>

      <template v-if="!loadingState">
        <!-- Not authenticated notice -->
        <div
          v-if="!isAuthenticated"
          class="mb-8 p-6 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg text-center"
        >
          <p class="text-text-secondary dark:text-text-secondary-dark mb-3">
            {{ $t('planetHall.notAuthenticated') }}
          </p>
          <a
            href="/"
            class="inline-block px-4 py-2 rounded-md bg-primary dark:bg-primary-dark text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            {{ $t('planetHall.loginButton') }}
          </a>
        </div>

        <!-- Messages section -->
        <section class="mb-12">
          <h2 class="text-xl font-semibold text-text-primary dark:text-text-primary-dark mb-4">
            {{ $t('planetHall.messages') }}
          </h2>

          <div
            v-if="messagesBuffer.length === 0"
            class="p-6 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg text-center text-text-secondary dark:text-text-secondary-dark"
          >
            {{ $t('planetHall.noMessages') }}
          </div>

          <div v-else class="space-y-3">
            <div
              v-for="msg in messagesBuffer"
              :key="msg._id || msg.id"
              class="p-4 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg"
            >
              <div class="flex items-start justify-between gap-2">
                <div>
                  <h3 class="font-medium text-text-primary dark:text-text-primary-dark">
                    {{ msg.payload?.subject || $t('planetHall.noSubject') }}
                  </h3>
                  <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
                    {{ msg.payload?.body || '' }}
                  </p>
                </div>
                <span
                  v-if="msg.created_at"
                  class="text-xs text-text-secondary dark:text-text-secondary-dark shrink-0"
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
          class="mb-12 p-6 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg"
        >
          <h2 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark mb-4">
            {{ $t('planetHall.sendMessage') }}
          </h2>

          <form @submit.prevent="handleCreateMessage" class="space-y-4">
            <div>
              <label class="block text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
                {{ $t('planetHall.subject') }}
              </label>
              <input
                v-model="newMessage.subject"
                type="text"
                required
                class="w-full px-3 py-2 rounded-md bg-bg-main dark:bg-bg-main-dark border border-border-light dark:border-border-dark text-text-primary dark:text-text-primary-dark text-sm focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-primary-light"
              />
            </div>
            <div>
              <label class="block text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
                {{ $t('planetHall.body') }}
              </label>
              <textarea
                v-model="newMessage.body"
                rows="3"
                required
                class="w-full px-3 py-2 rounded-md bg-bg-main dark:bg-bg-main-dark border border-border-light dark:border-border-dark text-text-primary dark:text-text-primary-dark text-sm focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-primary-light resize-y"
              ></textarea>
            </div>
            <div class="flex justify-end">
              <button
                type="submit"
                :disabled="messageSending"
                class="px-4 py-2 rounded-md bg-primary dark:bg-primary-dark text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {{ messageSending ? $t('planetHall.sending') : $t('planetHall.send') }}
              </button>
            </div>
          </form>
        </section>

        <!-- Requests section (auth required) -->
        <template v-if="isAuthenticated">
          <section class="mb-12">
            <h2 class="text-xl font-semibold text-text-primary dark:text-text-primary-dark mb-4">
              {{ $t('planetHall.requests') }}
            </h2>

            <div
              v-if="requestsBuffer.length === 0"
              class="p-6 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg text-center text-text-secondary dark:text-text-secondary-dark"
            >
              {{ $t('planetHall.noRequests') }}
            </div>

            <div v-else class="space-y-3">
              <div
                v-for="req in requestsBuffer"
                :key="req._id || req.id"
                class="p-4 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <h3 class="font-medium text-text-primary dark:text-text-primary-dark">
                      {{ req.request_type || $t('planetHall.unknownRequest') }}
                    </h3>
                    <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
                      {{ req.payload?.message || '' }}
                    </p>
                  </div>
                  <div class="text-right shrink-0">
                    <span
                      class="inline-block px-2 py-0.5 text-xs rounded-full"
                      :class="statusClass(req.status)"
                    >
                      {{ req.status }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- Create request form -->
          <section class="p-6 bg-bg-card dark:bg-bg-card-dark border border-border-light dark:border-border-dark rounded-lg">
            <h2 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark mb-4">
              {{ $t('planetHall.createRequest') }}
            </h2>

            <form @submit.prevent="handleCreateRequest" class="space-y-4">
              <div>
                <label class="block text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
                  {{ $t('planetHall.requestType') }}
                </label>
                <select
                  v-model="newRequest.request_type"
                  required
                  class="w-full px-3 py-2 rounded-md bg-bg-main dark:bg-bg-main-dark border border-border-light dark:border-border-dark text-text-primary dark:text-text-primary-dark text-sm focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-primary-light"
                >
                  <option value="allowance">{{ $t('planetHall.allowance') }}</option>
                  <option value="access">{{ $t('planetHall.access') }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm text-text-secondary dark:text-text-secondary-dark mb-1">
                  {{ $t('planetHall.message') }}
                </label>
                <textarea
                  v-model="newRequest.message"
                  rows="3"
                  required
                  class="w-full px-3 py-2 rounded-md bg-bg-main dark:bg-bg-main-dark border border-border-light dark:border-border-dark text-text-primary dark:text-text-primary-dark text-sm focus:outline-none focus:ring-2 focus:ring-primary dark:focus:ring-primary-light resize-y"
                ></textarea>
              </div>
              <div class="flex justify-end">
                <button
                  type="submit"
                  :disabled="requestSending"
                  class="px-4 py-2 rounded-md bg-primary dark:bg-primary-dark text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
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
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Use relative paths in production (through Traefik/Auth-Proxy), localhost in dev
const API_BASE = import.meta.env?.DEV ? 'http://localhost:5050' : ''

// ── Buffer Locals (REACTIVITY_ISOLATION.md) ──────────────────────────────
const messagesBuffer = ref<any[]>([])
const requestsBuffer = ref<any[]>([])
const loadingState = ref(true)
const errorMessage = ref('')
const planetOwnerId = ref('')
const isAuthenticated = ref(false)

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

// ── Helpers ──────────────────────────────────────────────────────────────

function formatDate(isoStr?: string) {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return isoStr
  }
}

function statusClass(status?: string) {
  switch (status) {
    case 'pending':
      return 'bg-yellow-900/30 text-yellow-300'
    case 'approved':
      return 'bg-green-900/30 text-green-300'
    case 'rejected':
      return 'bg-red-900/30 text-red-300'
    default:
      return 'bg-gray-900/30 text-gray-300'
  }
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const url = `${API_BASE}${path}`
  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  try {
    const response = await fetch(url, {
      credentials: 'include',
      headers: { ...defaultHeaders, ...(options.headers as Record<string, string>) },
      ...options,
    })
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(`HTTP ${response.status}: ${text || response.statusText}`)
    }
    return response.json()
  } catch (err) {
    errorMessage.value = (err as Error).message
    throw err
  }
}

// ── Auth Detection ───────────────────────────────────────────────────────

async function checkAuth() {
  try {
    const response = await fetch(`${API_BASE}/api/inbox/requests?status=pending`, {
      method: 'GET',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    })
    isAuthenticated.value = response.ok
  } catch {
    isAuthenticated.value = false
  }
}

// ── Data Loading ─────────────────────────────────────────────────────────

async function loadPlanetInfo() {
  try {
    const data: any = await apiFetch('/api/v1/auth/planet-info')
    planetOwnerId.value = data.planet_owner_id || ''
  } catch {
    // Non-critical: fallback handled at usage site
  }
}

async function loadMessages() {
  try {
    const data: any = await apiFetch('/api/inbox/messages')
    messagesBuffer.value = Array.isArray(data) ? data : []
  } catch {
    messagesBuffer.value = []
  }
}

async function loadRequests() {
  try {
    const data: any = await apiFetch('/api/inbox/requests')
    requestsBuffer.value = Array.isArray(data) ? data : []
  } catch {
    requestsBuffer.value = []
  }
}

async function loadData() {
  loadingState.value = true
  errorMessage.value = ''

  // First check if user has a session
  await checkAuth()

  // Always load planet info (public endpoint)
  // Only load messages/requests if authenticated
  const tasks = [loadPlanetInfo()]
  if (isAuthenticated.value) {
    tasks.push(loadMessages(), loadRequests())
  }

  await Promise.all(tasks)
  loadingState.value = false
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
  } catch {
    // errorMessage already set by apiFetch
  } finally {
    messageSending.value = false
  }
}

async function handleCreateRequest() {
  if (!newRequest.request_type || !newRequest.message) {
    errorMessage.value = 'Please fill in both request type and message.'
    return
  }
  if (!planetOwnerId.value) {
    errorMessage.value = 'Planet owner information not available. Please try again.'
    return
  }
  requestSending.value = true
  errorMessage.value = ''
  try {
    await apiFetch('/api/inbox/requests', {
      method: 'POST',
      body: JSON.stringify({
        target_user_id: planetOwnerId.value,
        request_type: newRequest.request_type,
        message: newRequest.message,
      }),
    })
    newRequest.request_type = 'allowance'
    newRequest.message = ''
    await loadRequests()
  } catch {
    // errorMessage already set by apiFetch
  } finally {
    requestSending.value = false
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────

onMounted(() => {
  loadData()
})
</script>
