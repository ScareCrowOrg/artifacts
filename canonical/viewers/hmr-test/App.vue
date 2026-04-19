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
import { ref, onMounted, inject } from 'vue'

const statusText = ref('Initializing...')
const statusDetail = ref('')
const statusClass = ref('success')
const status = ref('Session validated, WebSocket connected')
const sessionToken = inject<string | null>('sessionToken', null)

function updateStatus(text: string, detail: string = '', isError: boolean = false) {
  statusText.value = `Status: ${text}`
  statusDetail.value = detail
  statusClass.value = isError ? 'error' : 'success'
}

onMounted(() => {
  if (sessionToken) {
    console.log('[HMR-Test] Session valid (validated by Auth-Proxy), HMR ready')
    updateStatus('Ready', 'Session validated by Auth-Proxy\nEdit files to test HMR', false)
    status.value = 'HMR is active. Edit files and save to test hot reload.\nCheck browser console for WebSocket logs.'
  } else {
    console.error('[HMR-Test] No session token provided by ViewerShell')
    updateStatus(
      'Authentication Failed',
      'ViewerShell did not provide session token',
      true,
    )
  }
})
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
