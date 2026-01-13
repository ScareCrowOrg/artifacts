<template>
  <div class="log-toggle-cell bg-surface border border-border rounded-lg p-4">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-text-primary">
        Log Toggle Control
      </h3>
      <span 
        v-if="activeNamespaces.length > 0" 
        class="px-2 py-1 text-xs rounded bg-success text-white"
      >
        {{ activeNamespaces.length }} active
      </span>
    </div>

    <div class="mb-4">
      <p class="text-sm text-text-secondary mb-2">
        Temporarily enable/disable log namespaces for debugging. 
        Settings are session-based and won't persist after restart.
      </p>
    </div>

    <!-- Quick Actions -->
    <div class="flex gap-2 mb-4">
      <button
        @click="enableAll"
        class="px-3 py-1.5 text-sm rounded bg-primary text-white hover:bg-primary-dark transition-colors"
        :disabled="isAllEnabled"
      >
        Enable All
      </button>
      <button
        @click="disableAll"
        class="px-3 py-1.5 text-sm rounded bg-gray-500 text-white hover:bg-gray-600 transition-colors"
        :disabled="activeNamespaces.length === 0"
      >
        Disable All
      </button>
      <button
        @click="applyChanges"
        class="px-3 py-1.5 text-sm rounded bg-success text-white hover:bg-success-dark transition-colors ml-auto"
        :disabled="!hasChanges"
      >
        Apply Changes
      </button>
    </div>

    <!-- Search Filter -->
    <div class="mb-4">
      <input
        v-model="searchFilter"
        type="text"
        placeholder="Search namespaces..."
        class="w-full px-3 py-2 border border-border rounded bg-surface text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        :disabled="namespacesLoading"
      />
    </div>

    <!-- Loading State -->
    <div v-if="namespacesLoading" class="text-center py-8 text-text-secondary">
      <div class="animate-pulse">Loading namespaces...</div>
    </div>

    <!-- Error State -->
    <div v-else-if="namespacesError" class="mb-4 p-3 bg-error bg-opacity-10 border border-error rounded">
      <p class="text-sm text-error">
        Failed to load namespaces from API: {{ namespacesError }}
      </p>
      <p class="text-xs text-text-secondary mt-1">
        Using fallback namespace list
      </p>
    </div>

    <!-- Namespace List -->
    <div v-else class="space-y-2 max-h-96 overflow-y-auto">
      <div
        v-for="namespace in filteredNamespaces"
        :key="namespace"
        class="flex items-center justify-between p-2 rounded hover:bg-hover transition-colors"
      >
        <label class="flex items-center flex-1 cursor-pointer">
          <input
            type="checkbox"
            :checked="isNamespaceEnabled(namespace)"
            @change="toggleNamespace(namespace)"
            class="mr-3 w-4 h-4 rounded border-border text-primary focus:ring-primary"
          />
          <span class="text-sm font-mono text-text-primary">{{ namespace }}</span>
        </label>
        <span
          v-if="isNamespaceEnabled(namespace)"
          class="text-xs text-success"
        >
          ✓ Active
        </span>
      </div>
      
      <div v-if="filteredNamespaces.length === 0" class="text-center py-8 text-text-secondary">
        No namespaces match your search
      </div>
    </div>

    <!-- Current Pattern Display -->
    <div class="mt-4 p-3 bg-hover rounded border border-border">
      <div class="text-xs text-text-secondary mb-1">Current DEBUG Pattern:</div>
      <div class="font-mono text-sm text-text-primary break-all">
        {{ currentPattern || '(none - all logs disabled)' }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import type { Ref, ComputedRef } from 'vue'

// Note: In a real Vue 3 SFC setup, você deve importar apiService para garantir headers de autenticação
import apiService from '@/services/apiService'
// Import logger runtime configuration functions
import { setDebugPattern, getDebugPatternValue, getRegisteredNamespaces } from '@/utils/logger'

// Define props interface
interface CellData {
  enabled_namespaces?: string[]
  debug_pattern?: string
}

interface Props {
  cell: {
    initial_data?: CellData
  }
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
}>()

// Available log namespaces
// Fetched dynamically from backend API
const availableNamespaces: Ref<string[]> = ref([])
const namespacesLoading: Ref<boolean> = ref(false)
const namespacesError: Ref<string | null> = ref(null)

// State
const activeNamespaces: Ref<string[]> = ref(props.cell.initial_data?.enabled_namespaces || [])
const searchFilter: Ref<string> = ref('')
const originalNamespaces: Ref<string[]> = ref([...activeNamespaces.value])

// Computed properties
const filteredNamespaces: ComputedRef<string[]> = computed(() => {
  if (!searchFilter.value) {
    return availableNamespaces.value
  }
  
  const filter = searchFilter.value.toLowerCase()
  return availableNamespaces.value.filter(ns => 
    ns.toLowerCase().includes(filter)
  )
})

const currentPattern: ComputedRef<string> = computed(() => {
  if (activeNamespaces.value.length === 0) {
    return ''
  }
  
  if (activeNamespaces.value.length === availableNamespaces.value.length) {
    return '*'
  }
  
  return activeNamespaces.value.join(',')
})

const isAllEnabled: ComputedRef<boolean> = computed(() => {
  return activeNamespaces.value.length === availableNamespaces.value.length
})

const hasChanges: ComputedRef<boolean> = computed(() => {
  if (activeNamespaces.value.length !== originalNamespaces.value.length) {
    return true
  }
  
  const sorted1 = [...activeNamespaces.value].sort()
  const sorted2 = [...originalNamespaces.value].sort()
  
  return !sorted1.every((val, index) => val === sorted2[index])
})

// Watch for external changes to cell data
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    activeNamespaces.value = newData.enabled_namespaces || []
    originalNamespaces.value = [...activeNamespaces.value]
  }
}, { deep: true })

// Methods
function isNamespaceEnabled(namespace: string): boolean {
  return activeNamespaces.value.includes(namespace)
}

function toggleNamespace(namespace: string): void {
  const index = activeNamespaces.value.indexOf(namespace)
  
  if (index > -1) {
    activeNamespaces.value = activeNamespaces.value.filter(ns => ns !== namespace)
  } else {
    activeNamespaces.value = [...activeNamespaces.value, namespace]
  }
}

function enableAll(): void {
  activeNamespaces.value = [...availableNamespaces.value]
}

function disableAll(): void {
  activeNamespaces.value = []
}

function applyChanges(): void {
  originalNamespaces.value = [...activeNamespaces.value]
  
  // Update the runtime DEBUG pattern in localStorage
  const pattern = currentPattern.value
  setDebugPattern(pattern)
  
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      enabled_namespaces: activeNamespaces.value,
      debug_pattern: pattern
    }
  })
  
  console.log(`[log-toggle-cell] Applied DEBUG pattern: ${pattern || '(none)'}`)
}

// Fetch available namespaces from backend API
async function fetchAvailableNamespaces(): Promise<void> {
  namespacesLoading.value = true
  namespacesError.value = null
  
  try {
    // Usando apiService para garantir headers de autenticação e tratamento de sessão expirada
    const response = await apiService.fetch('/api/logs/namespaces', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    })
    if (!response.ok) {
      throw new Error(`Failed to fetch namespaces: ${response.statusText}`)
    }
    const namespaces = await response.json()
    availableNamespaces.value = namespaces
  } catch (error) {
    console.error('Error fetching log namespaces:', error)
    namespacesError.value = error instanceof Error ? error.message : 'Unknown error'
    
    // Fallback: Use registered namespaces from logger + common defaults
    const registeredNamespaces = getRegisteredNamespaces()
    const defaultNamespaces = [
      'app',
      'auth',
      'api',
      'store',
      'router',
      'debug',
      'component',
      'websocket',
      'extension'
    ]
    
    // Merge and deduplicate
    const combined = [...new Set([...registeredNamespaces, ...defaultNamespaces])]
    availableNamespaces.value = combined.sort()
  } finally {
    namespacesLoading.value = false
  }
}

// Lifecycle
onMounted(() => {
  // Fetch available namespaces from backend
  fetchAvailableNamespaces()
  
  // Load current DEBUG pattern from localStorage
  const currentDebug = getDebugPatternValue()
  if (currentDebug) {
    // Parse current pattern to initialize active namespaces
    if (currentDebug === '*') {
      // Will be set after namespaces are loaded
    } else {
      activeNamespaces.value = currentDebug.split(',').map(ns => ns.trim()).filter(Boolean)
      originalNamespaces.value = [...activeNamespaces.value]
    }
  }
})
</script>

<style scoped>
/* Additional custom styles if needed */
.log-toggle-cell input[type="checkbox"]:checked {
  @apply bg-primary border-primary;
}
</style>
