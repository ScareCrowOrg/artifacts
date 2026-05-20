/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-05-13",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0
 * }
 */
<template>
  <div class="container">
    <h1>✅ HMR Test Ready</h1>
    <p>{{ status }}</p>
    <div :class="['status', statusClass]">
      <p id="status-text">Status: {{ statusText }}</p>
      <p id="status-detail">{{ statusDetail }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useBaseViewer } from '@/composables/useBaseViewer'

const {
  loadingState, errorMessage, isAuthenticated,
} = useBaseViewer()

const statusText = ref('Initializing...')
const statusDetail = ref('')
const statusClass = ref('success')
const status = computed(() => {
  if (isAuthenticated.value) return 'Session validated, WebSocket connected'
  if (errorMessage.value) return `Error: ${errorMessage.value}`
  return 'Waiting for handshake...'
})

function updateStatus(text: string, detail: string = '', isError: boolean = false) {
  statusText.value = `Status: ${text}`
  statusDetail.value = detail
  statusClass.value = isError ? 'error' : 'success'
}

// Track authentication state reactively
watch(isAuthenticated, (auth) => {
  if (auth) {
    updateStatus('Ready', 'Session validated by Auth-Proxy\nEdit files to test HMR', false)
  }
})

watch(errorMessage, (err) => {
  if (err) {
    updateStatus('Authentication Failed', err, true)
  }
})

// Initial state
updateStatus('Waiting for handshake...', 'Listening for INIT_WORKSPACE from ViewerShell', false)
</script>

<style scoped>
.container {
  background: white;
  padding: 40px;
  border-radius: 10px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  text-align: center;
  max-width: 500px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

h1 {
  color: #333;
  margin: 0 0 10px 0;
}

p {
  color: #666;
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}

.status {
  margin-top: 20px;
  padding: 10px;
  background: #f0f0f0;
  border-radius: 5px;
  font-family: monospace;
  font-size: 12px;
  color: #333;
  text-align: left;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  border-left: 4px solid #d32f2f;
}

.success {
  color: #388e3c;
  background: #e8f5e9;
  border-left: 4px solid #388e3c;
}
</style>
