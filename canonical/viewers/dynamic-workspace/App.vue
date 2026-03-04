<template>
  <div class="dynamic-workspace-v2">
    <!-- Status indicator -->
    <div class="status-badge" :class="statusClass">
      {{ statusLabel }}
    </div>

    <!-- Hello World message (Phase 1 MVP) -->
    <h1 class="workspace-title">Dynamic Workspace v2 – Ready</h1>

    <p v-if="store.status === 'pending'" class="workspace-subtitle">
      Waiting for handshake from Cockpit…
    </p>

    <p v-else-if="store.status === 'ready'" class="workspace-subtitle">
      Handshake complete ✅ — workspace {{ store.workspaceId }} is live.
    </p>

    <p v-else-if="store.status === 'error'" class="workspace-subtitle workspace-error">
      {{ store.errorMessage || 'Unknown error during handshake.' }}
    </p>

    <!-- Debug info (dev only) -->
    <pre v-if="isDev" class="workspace-debug">{{ debugInfo }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWorkspaceHandshake } from './composables/useWorkspaceHandshake'

// Activate the handshake listener
const { store } = useWorkspaceHandshake()

const isDev = import.meta.env.DEV

const statusClass = computed(() => ({
  'status-pending': store.status === 'pending',
  'status-ready': store.status === 'ready',
  'status-error': store.status === 'error',
}))

const statusLabel = computed(() => {
  switch (store.status) {
    case 'ready':
      return '🟢 Ready'
    case 'error':
      return '🔴 Error'
    default:
      return '🟡 Pending'
  }
})

const debugInfo = computed(() =>
  JSON.stringify(
    {
      workspaceId: store.workspaceId,
      userId: store.userId,
      status: store.status,
      errorCode: store.errorCode,
    },
    null,
    2,
  ),
)
</script>

<style scoped>
.dynamic-workspace-v2 {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
  font-family: system-ui, sans-serif;
  background: #0f172a;
  color: #f1f5f9;
  gap: 1rem;
}

.workspace-title {
  font-size: 1.75rem;
  font-weight: 700;
  margin: 0;
  color: #38bdf8;
}

.workspace-subtitle {
  font-size: 1rem;
  color: #94a3b8;
  text-align: center;
  margin: 0;
}

.workspace-error {
  color: #f87171;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 600;
}

.status-pending {
  background: #78350f;
  color: #fde68a;
}

.status-ready {
  background: #14532d;
  color: #86efac;
}

.status-error {
  background: #7f1d1d;
  color: #fca5a5;
}

.workspace-debug {
  margin-top: 1rem;
  padding: 1rem;
  background: #1e293b;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  color: #94a3b8;
  text-align: left;
  max-width: 480px;
  width: 100%;
  overflow: auto;
}
</style>
