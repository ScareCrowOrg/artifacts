/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="redis-explorer-cell bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-4 h-full flex flex-col">
    <!-- Header with Redis Info -->
    <div class="flex justify-between items-center mb-4 pb-3 border-b border-border dark:border-border-dark">
      <h3 class="text-lg font-semibold theme-text-primary">
        Redis Explorer
      </h3>
      <div v-if="redisInfo" class="flex items-center gap-4 text-sm theme-text-secondary">
        <span>{{ redisInfo.total_keys }} keys</span>
        <span>{{ redisInfo.used_memory }}</span>
        <span class="px-2 py-1 rounded bg-primary/10 dark:bg-primary/20 text-primary dark:text-primary-light">
          {{ redisInfo.version }}
        </span>
      </div>
    </div>

    <!-- Breadcrumb Navigation -->
    <div class="mb-4 flex items-center gap-2 text-sm">
      <button
        class="px-3 py-1 rounded hover:bg-surface-dark/10 dark:hover:bg-surface/10 theme-text-primary"
        @click="navigateToPrefix('')"
      >
        🏠 Root
      </button>
      <template v-for="(segment, index) in prefixSegments" :key="index">
        <span class="theme-text-secondary">›</span>
        <button
          class="px-3 py-1 rounded hover:bg-surface-dark/10 dark:hover:bg-surface/10 theme-text-primary"
          @click="navigateToSegment(index)"
        >
          {{ segment }}
        </button>
      </template>
    </div>

    <!-- Error Display -->
    <div v-if="error" class="mb-4 p-3 bg-red-50 dark:bg-red-950 border border-red-300 dark:border-red-700 rounded text-red-700 dark:text-red-400">
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-hidden flex gap-4">
      <!-- Left Panel: Tree Navigation -->
      <div class="w-1/2 flex flex-col border border-border dark:border-border-dark rounded bg-surface/50 dark:bg-surface-dark/50">
        <div class="p-3 border-b border-border dark:border-border-dark bg-surface/80 dark:bg-surface-dark/80">
          <h4 class="font-semibold theme-text-primary">Navigation</h4>
        </div>
        
        <div class="flex-1 overflow-y-auto p-3">
          <!-- Loading State -->
          <div v-if="loading" class="flex items-center justify-center h-full">
            <div class="text-center">
              <div class="spinner mb-2"></div>
              <p class="text-sm theme-text-secondary">Scanning keys...</p>
            </div>
          </div>

          <!-- Nodes (Branch Prefixes) -->
          <div v-else-if="scanResult">
            <div v-if="scanResult.nodes.length > 0" class="mb-4">
              <h5 class="text-sm font-semibold theme-text-secondary mb-2">Branches ({{ scanResult.nodes.length }})</h5>
              <div class="space-y-1">
                <button
                  v-for="node in scanResult.nodes"
                  :key="node"
                  class="w-full text-left px-3 py-2 rounded hover:bg-primary/10 dark:hover:bg-primary/20 theme-text-primary flex items-center gap-2 transition-colors"
                  @click="navigateToNode(node)"
                >
                  <span class="text-lg">📁</span>
                  <span class="font-mono">{{ node }}</span>
                </button>
              </div>
            </div>

            <!-- Final Keys -->
            <div v-if="scanResult.keys.length > 0">
              <h5 class="text-sm font-semibold theme-text-secondary mb-2">Keys ({{ scanResult.keys.length }})</h5>
              <div class="space-y-1">
                <button
                  v-for="key in scanResult.keys"
                  :key="key"
                  class="w-full text-left px-3 py-2 rounded hover:bg-primary/10 dark:hover:bg-primary/20 theme-text-primary flex items-center gap-2 transition-colors"
                  :class="{ 'bg-primary/20 dark:bg-primary/30': selectedKey === key }"
                  @click="selectKey(key)"
                >
                  <span class="text-lg">🔑</span>
                  <span class="font-mono text-sm truncate">{{ formatKeyName(key) }}</span>
                </button>
              </div>
            </div>

            <!-- Empty State -->
            <div v-if="scanResult.nodes.length === 0 && scanResult.keys.length === 0" class="text-center py-8">
              <p class="theme-text-secondary">No keys or branches found at this level</p>
            </div>

            <!-- Actions for Current Level -->
            <div v-if="currentPrefix" class="mt-4 pt-4 border-t border-border dark:border-border-dark">
              <button
                class="w-full px-3 py-2 rounded bg-red-50 dark:bg-red-950 border border-red-300 dark:border-red-700 text-red-700 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900 transition-colors"
                @click="showDeleteConfirmation"
              >
                🗑️ Delete Branch
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Panel: Key Value Viewer -->
      <div class="w-1/2 flex flex-col border border-border dark:border-border-dark rounded bg-surface/50 dark:bg-surface-dark/50">
        <div class="p-3 border-b border-border dark:border-border-dark bg-surface/80 dark:bg-surface-dark/80">
          <h4 class="font-semibold theme-text-primary">Key Inspector</h4>
        </div>
        
        <div class="flex-1 overflow-y-auto p-3">
          <!-- No Key Selected -->
          <div v-if="!selectedKey && !keyValue" class="flex items-center justify-center h-full text-center">
            <div>
              <span class="text-5xl mb-3 block">🔍</span>
              <p class="theme-text-secondary">Select a key to inspect its value</p>
            </div>
          </div>

          <!-- Loading Key Value -->
          <div v-else-if="loadingKeyValue" class="flex items-center justify-center h-full">
            <div class="text-center">
              <div class="spinner mb-2"></div>
              <p class="text-sm theme-text-secondary">Loading key value...</p>
            </div>
          </div>

          <!-- Key Value Display -->
          <div v-else-if="keyValue" class="space-y-4">
            <!-- Key Metadata -->
            <div class="space-y-2">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <label class="text-xs font-semibold theme-text-secondary uppercase">Key</label>
                  <p class="font-mono text-sm theme-text-primary break-all">{{ keyValue.key }}</p>
                </div>
                <button
                  class="px-2 py-1 text-xs rounded hover:bg-surface-dark/10 dark:hover:bg-surface/10 theme-text-primary"
                  title="Copy key to clipboard"
                  @click="copyToClipboard(keyValue.key)"
                >
                  📋 Copy
                </button>
              </div>

              <div class="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <label class="font-semibold theme-text-secondary uppercase">Type</label>
                  <p class="theme-text-primary">{{ keyValue.type }}</p>
                </div>
                <div>
                  <label class="font-semibold theme-text-secondary uppercase">TTL</label>
                  <p class="theme-text-primary">{{ formatTTL(keyValue.ttl) }}</p>
                </div>
                <div v-if="keyValue.size">
                  <label class="font-semibold theme-text-secondary uppercase">Size</label>
                  <p class="theme-text-primary">{{ formatBytes(keyValue.size) }}</p>
                </div>
              </div>
            </div>

            <!-- Value Display -->
            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="text-xs font-semibold theme-text-secondary uppercase">Value</label>
                <button
                  class="px-2 py-1 text-xs rounded hover:bg-surface-dark/10 dark:hover:bg-surface/10 theme-text-primary"
                  title="Copy value to clipboard"
                  @click="copyToClipboard(formatValue(keyValue.value))"
                >
                  📋 Copy
                </button>
              </div>
              <pre class="p-3 bg-surface-dark/10 dark:bg-surface/10 rounded text-xs font-mono overflow-x-auto theme-text-primary">{{ formatValue(keyValue.value) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div
      v-if="showDeleteModal"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      @click.self="closeDeleteModal"
    >
      <div class="bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 class="text-lg font-bold theme-text-primary mb-4">⚠️ Confirm Deletion</h3>
        
        <div class="space-y-3 mb-6">
          <p class="theme-text-primary">
            You are about to delete all keys matching this pattern:
          </p>
          <p class="font-mono text-sm px-3 py-2 bg-red-50 dark:bg-red-950 border border-red-300 dark:border-red-700 rounded theme-text-primary">
            {{ deletePattern }}*
          </p>
          
          <div v-if="deletePreview" class="text-sm">
            <p class="theme-text-secondary mb-2">
              <strong>{{ deletePreview.keys_found }}</strong> key(s) will be deleted:
            </p>
            <div v-if="deletePreview.sample_keys.length > 0" class="max-h-32 overflow-y-auto p-2 bg-surface-dark/10 dark:bg-surface/10 rounded">
              <ul class="space-y-1 font-mono text-xs theme-text-primary">
                <li v-for="key in deletePreview.sample_keys" :key="key">• {{ key }}</li>
              </ul>
              <p v-if="deletePreview.keys_found > deletePreview.sample_keys.length" class="mt-2 theme-text-secondary italic">
                ... and {{ deletePreview.keys_found - deletePreview.sample_keys.length }} more
              </p>
            </div>
          </div>
        </div>

        <div class="flex gap-3">
          <button
            class="flex-1 px-4 py-2 rounded border border-border dark:border-border-dark hover:bg-surface-dark/10 dark:hover:bg-surface/10 theme-text-primary transition-colors"
            @click="closeDeleteModal"
          >
            Cancel
          </button>
          <button
            class="flex-1 px-4 py-2 rounded bg-red-600 dark:bg-red-700 text-white hover:bg-red-700 dark:hover:bg-red-800 transition-colors"
            :disabled="deletingKeys"
            @click="confirmDelete"
          >
            {{ deletingKeys ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, type Ref } from 'vue'
import { createLogger } from '#shared/logger.js'
import { apiFetch } from '@/services/apiService'
const logger = createLogger('cell:redis-explorer')

// Define props interface
interface Props {
  cell: {
    id?: string
    initial_data?: {
      current_prefix?: string
      delimiter?: string
      max_depth?: number
    }
  }
}

const props = defineProps<Props>()

// Typed emits
const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
}>()

// Types for Redis API responses
interface RedisInfo {
  version: string
  used_memory: string
  total_keys: number
  connected_clients: number
  uptime_seconds: number
}

interface ScanResult {
  prefix: string
  delimiter: string
  nodes: string[]
  keys: string[]
  total_scanned: number
}

interface KeyValue {
  key: string
  type: string
  value: any
  ttl: number
  size: number | null
}

interface DeletePreview {
  prefix: string
  keys_found: number
  keys_deleted: number
  dry_run: boolean
  sample_keys: string[]
}

// State
const currentPrefix: Ref<string> = ref(props.cell.initial_data?.current_prefix || '')
const delimiter: Ref<string> = ref(props.cell.initial_data?.delimiter || ':')
const maxDepth: Ref<number> = ref(props.cell.initial_data?.max_depth || 1)

const redisInfo: Ref<RedisInfo | null> = ref(null)
const scanResult: Ref<ScanResult | null> = ref(null)
const selectedKey: Ref<string> = ref('')
const keyValue: Ref<KeyValue | null> = ref(null)

const loading: Ref<boolean> = ref(false)
const loadingKeyValue: Ref<boolean> = ref(false)
const error: Ref<string> = ref('')

const showDeleteModal: Ref<boolean> = ref(false)
const deletePattern: Ref<string> = ref('')
const deletePreview: Ref<DeletePreview | null> = ref(null)
const deletingKeys: Ref<boolean> = ref(false)

// Computed
const prefixSegments = computed<string[]>(() => {
  if (!currentPrefix.value) return []
  return currentPrefix.value.split(delimiter.value).filter(Boolean)
})

// Methods
async function loadRedisInfo(): Promise<void> {
  try {
    const response = await apiFetch('/api/redis-explorer/info', {
      headers: {
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error('Failed to load Redis info')
    }
    
    redisInfo.value = await response.json()
    logger.info('Redis info loaded', { totalKeys: redisInfo.value?.total_keys })
  } catch (err) {
    logger.error('Failed to load Redis info', err)
    error.value = err instanceof Error ? err.message : 'Unknown error'
  }
}

async function scanKeys(): Promise<void> {
  loading.value = true
  error.value = ''
  
  try {
    logger.debug('Scanning keys', { prefix: currentPrefix.value })
    
    const response = await apiFetch('/api/redis-explorer/scan', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prefix: currentPrefix.value,
        delimiter: delimiter.value,
        max_depth: maxDepth.value
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to scan Redis keys')
    }
    
    scanResult.value = await response.json()
    logger.info('Keys scanned', {
      nodes: scanResult.value?.nodes.length,
      keys: scanResult.value?.keys.length
    })
  } catch (err) {
    logger.error('Failed to scan keys', err)
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

async function selectKey(key: string): Promise<void> {
  selectedKey.value = key
  loadingKeyValue.value = true
  keyValue.value = null
  error.value = ''
  
  try {
    logger.debug('Loading key value', { key })
    
    const response = await apiFetch(`/api/redis-explorer/key/${encodeURIComponent(key)}`, {
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (!response.ok) {
      throw new Error('Failed to load key value')
    }
    
    keyValue.value = await response.json()
    logger.info('Key value loaded', { key, type: keyValue.value?.type })
  } catch (err) {
    logger.error('Failed to load key value', err)
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    loadingKeyValue.value = false
  }
}

function navigateToPrefix(prefix: string): void {
  currentPrefix.value = prefix
  selectedKey.value = ''
  keyValue.value = null
  scanKeys()
  updateCell()
}

function navigateToNode(node: string): void {
  const newPrefix = currentPrefix.value 
    ? `${currentPrefix.value}${delimiter.value}${node}`
    : node
  navigateToPrefix(newPrefix)
}

function navigateToSegment(index: number): void {
  const segments = prefixSegments.value.slice(0, index + 1)
  navigateToPrefix(segments.join(delimiter.value))
}

async function showDeleteConfirmation(): Promise<void> {
  if (!currentPrefix.value) {
    error.value = 'Cannot delete from root level'
    return
  }
  
  deletePattern.value = currentPrefix.value
  showDeleteModal.value = true
  
  // Load preview
  try {
    const response = await apiFetch('/api/redis-explorer/delete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prefix: deletePattern.value,
        dry_run: true,
        confirm: false
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to preview deletion')
    }
    
    deletePreview.value = await response.json()
    logger.info('Delete preview loaded', { keysFound: deletePreview.value?.keys_found })
  } catch (err) {
    logger.error('Failed to load delete preview', err)
    error.value = err instanceof Error ? err.message : 'Unknown error'
  }
}

async function confirmDelete(): Promise<void> {
  deletingKeys.value = true
  
  try {
    logger.warn('Deleting keys', { pattern: deletePattern.value })
    
    const response = await apiFetch('/api/redis-explorer/delete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prefix: deletePattern.value,
        dry_run: false,
        confirm: true
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to delete keys')
    }
    
    const result: DeletePreview = await response.json()
    logger.info('Keys deleted', { count: result.keys_deleted })
    
    // Navigate up one level after deletion
    const segments = prefixSegments.value
    if (segments.length > 0) {
      segments.pop()
      navigateToPrefix(segments.join(delimiter.value))
    } else {
      navigateToPrefix('')
    }
    
    closeDeleteModal()
  } catch (err) {
    logger.error('Failed to delete keys', err)
    error.value = err instanceof Error ? err.message : 'Unknown error'
  } finally {
    deletingKeys.value = false
  }
}

function closeDeleteModal(): void {
  showDeleteModal.value = false
  deletePattern.value = ''
  deletePreview.value = null
}

function formatKeyName(key: string): string {
  // Show only the last segment after current prefix
  if (currentPrefix.value && key.startsWith(currentPrefix.value)) {
    return key.substring(currentPrefix.value.length + delimiter.value.length)
  }
  return key
}

function formatValue(value: any): string {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function formatTTL(ttl: number): string {
  if (ttl === -1) return 'No expiry'
  if (ttl === -2) return 'Key not found'
  if (ttl < 60) return `${ttl}s`
  if (ttl < 3600) return `${Math.floor(ttl / 60)}m`
  if (ttl < 86400) return `${Math.floor(ttl / 3600)}h`
  return `${Math.floor(ttl / 86400)}d`
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    logger.info('Copied to clipboard')
  } catch (err) {
    logger.error('Failed to copy to clipboard', err)
  }
}

function updateCell(): void {
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      current_prefix: currentPrefix.value,
      delimiter: delimiter.value,
      max_depth: maxDepth.value
    }
  })
}

// Watch for prop changes
watch(() => props.cell.initial_data, (newData) => {
  if (newData) {
    if (newData.current_prefix !== undefined) {
      currentPrefix.value = newData.current_prefix
    }
    if (newData.delimiter !== undefined) {
      delimiter.value = newData.delimiter
    }
    if (newData.max_depth !== undefined) {
      maxDepth.value = newData.max_depth
    }
  }
}, { deep: true })

// Initialize on mount
onMounted(() => {
  logger.info('Redis Explorer Cell mounted')
  loadRedisInfo()
  scanKeys()
})
</script>

<style scoped>
.spinner {
  border: 3px solid var(--color-border);
  border-top: 3px solid var(--color-primary);
  border-radius: 50%;
  width: 24px;
  height: 24px;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
