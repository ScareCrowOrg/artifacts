<template>
  <div class="content-selection-cell bg-surface border border-border rounded-lg p-4">
    <!-- Header -->
    <div class="flex items-center gap-2 mb-4">
      <svg class="w-6 h-6 text-primary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
      </svg>
      <h3 class="text-lg font-semibold">Content Selection</h3>
      <button
        class="ml-auto p-1.5 rounded hover:bg-surface-alt transition-colors"
        :disabled="isLoading"
        @click="loadContents"
        title="Refresh content list"
      >
        <svg class="w-4 h-4 text-text-secondary" :class="{ 'animate-spin': isLoading }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>

    <!-- Filters -->
    <div class="flex flex-col sm:flex-row gap-2 mb-4">
      <select
        class="flex-1 px-3 py-2 text-sm bg-surface border border-border rounded-md focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
        :value="localContentTypeFilter"
        @change="handleFilterChange"
        :disabled="isLoading"
      >
        <option value="">All Types</option>
        <option value="image-png">image-png</option>
        <option value="vector-svg">vector-svg</option>
        <option value="3d-glb">3d-glb</option>
      </select>
      <div class="relative flex-1">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          class="w-full pl-9 pr-3 py-2 text-sm bg-surface border border-border rounded-md focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none"
          type="text"
          placeholder="Search by filename..."
          v-model="localSearchQuery"
          @input="handleSearchInput"
          :disabled="isLoading"
        />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center gap-3 py-12 text-text-secondary">
      <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      <span class="text-sm">Loading content list...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="localError" class="p-4 bg-error/10 border border-error/30 rounded text-error text-sm">
      <div class="flex items-start gap-2">
        <svg class="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>{{ localError }}</span>
      </div>
      <button
        class="mt-3 px-3 py-1.5 text-xs font-medium bg-error/10 border border-error/30 rounded hover:bg-error/20 transition-colors"
        @click="loadContents"
      >
        Retry
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="localContents.length === 0" class="flex flex-col items-center justify-center gap-2 py-12 text-text-secondary">
      <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p class="text-sm font-medium">No content found</p>
      <p class="text-xs">
        {{ localContentTypeFilter ? `No "${localContentTypeFilter}" content available.` : 'Upload content first using the Content Upload cell.' }}
      </p>
    </div>

    <!-- Content List (table) -->
    <div v-else class="space-y-3">
      <div class="overflow-x-auto border border-border rounded-lg">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-surface-alt text-text-secondary text-left">
              <th class="px-3 py-2 font-medium">Name</th>
              <th class="px-3 py-2 font-medium">Type</th>
              <th class="px-3 py-2 font-medium text-right">Size</th>
              <th class="px-3 py-2 font-medium text-right hidden sm:table-cell">Created</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="content in localContents"
              :key="content.id"
              class="border-t border-border cursor-pointer transition-colors hover:bg-surface-alt"
              :class="{
                'bg-primary/10 hover:bg-primary/15 ring-1 ring-primary/40': localSelectedContent?.id === content.id
              }"
              @click="handleSelect(content)"
            >
              <td class="px-3 py-2.5">
                <div class="flex items-center gap-2">
                  <svg v-if="localSelectedContent?.id === content.id" class="w-4 h-4 text-primary flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                  </svg>
                  <svg v-else class="w-4 h-4 text-text-secondary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <div class="flex flex-col min-w-0">
                    <span
                      class="font-medium text-text-primary truncate"
                      :title="content.fragments?.name || content.filename"
                    >
                      {{ content.fragments?.name || content.filename }}
                    </span>
                    <span class="text-xs text-text-secondary truncate">
                      {{ content.filename }}
                    </span>
                  </div>
                </div>
              </td>
              <td class="px-3 py-2.5">
                <span class="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full"
                  :class="contentTypeBadgeClass(content.content_type_id || content.content_type)">
                  {{ content.content_type_id || content.content_type || 'unknown' }}
                </span>
              </td>
              <td class="px-3 py-2.5 text-right text-text-secondary whitespace-nowrap">
                {{ formatFileSize(content.size_bytes || 0) }}
              </td>
              <td class="px-3 py-2.5 text-right text-text-secondary whitespace-nowrap hidden sm:table-cell">
                {{ formatDate(content.created_at) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between text-sm text-text-secondary">
        <span v-if="localTotal > 0">
          Showing {{ localOffset + 1 }}-{{ Math.min(localOffset + localLimit, localTotal) }} of {{ localTotal }}
        </span>
        <span v-else>&nbsp;</span>
        <div class="flex items-center gap-1">
          <button
            class="px-3 py-1.5 text-xs font-medium border border-border rounded hover:bg-surface-alt disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="localOffset <= 0 || isLoading"
            @click="handlePageChange('prev')"
          >
            ← Previous
          </button>
          <button
            class="px-3 py-1.5 text-xs font-medium border border-border rounded hover:bg-surface-alt disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="localOffset + localLimit >= localTotal || isLoading"
            @click="handlePageChange('next')"
          >
            Next →
          </button>
        </div>
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="flex items-center gap-2 mt-4 pt-3 border-t border-border">
      <button
        class="flex-1 px-4 py-2 text-sm font-medium border border-border rounded-md hover:bg-surface-alt transition-colors"
        :disabled="isLoading"
        @click="clearSelection"
      >
        Cancel
      </button>
      <button
        class="flex-1 px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        :disabled="!localSelectedContent || isLoading"
        @click="confirmSelection"
      >
        <svg v-if="localSelectedContent" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        {{ localSelectedContent ? `Select: ${localSelectedContent.fragments?.name || localSelectedContent.filename}` : 'Select Content' }}
      </button>
    </div>

    <!-- Selection Result Confirmation -->
    <div v-if="selectionConfirmed" class="mt-3 p-3 bg-success/10 border border-success/30 rounded text-sm">
      <div class="flex items-center gap-2 text-success font-medium mb-1">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Content Selected
      </div>
      <div class="space-y-1 text-text-primary text-xs">
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[80px]">Content ID:</span>
          <code class="bg-surface-alt px-1.5 py-0.5 rounded truncate">{{ selectionResult.selected_content_id }}</code>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[80px]">Name:</span>
          <span>{{ selectionResult.selected_name }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[80px]">File:</span>
          <span>{{ selectionResult.selected_filename }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, type Ref } from 'vue'
import { ContentSelectionCell } from './ContentSelectionCell'
import type { CellResult, ValidationError } from '@/types/BaseCell'

// ── Props ──────────────────────────────────────────────────────────────
interface ContentItem {
  id: string
  content_type_id?: string
  content_type?: string
  filename: string
  size_bytes?: number
  created_at?: string
  data_ref?: string
  tags?: string[]
  version?: number
  is_latest?: boolean
  fragments?: Record<string, any>
}

interface Props {
  cell?: {
    id?: string
    initial_data?: {
      content_type_id?: string | null
      category?: string
      allow_multiple?: boolean
      view_mode?: string
    }
  }
}

const props = withDefaults(defineProps<Props>(), {
  cell: () => ({})
})

const emit = defineEmits<{
  'update:cell': [cell: Props['cell']]
  execute: []
}>()

// ── Buffer Local State (Buffer Local Pattern) ──────────────────────────
const cellInstance: Ref<ContentSelectionCell | null> = ref(null)

// Content list
const localContents: Ref<ContentItem[]> = ref([])
const localTotal: Ref<number> = ref(0)
const localLimit: Ref<number> = ref(20)
const localOffset: Ref<number> = ref(0)

// Filters
const localContentTypeFilter: Ref<string> = ref('')
const localSearchQuery: Ref<string> = ref('')
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

// Selection
const localSelectedContent: Ref<ContentItem | null> = ref(null)
const selectionConfirmed: Ref<boolean> = ref(false)
const selectionResult: Ref<Record<string, any>> = ref({})

// UI states
const isLoading: Ref<boolean> = ref(false)
const localError: Ref<string | null> = ref(null)

// ── Hydration (Buffer Local Pattern Step 1) ────────────────────────────
onMounted(() => {
  cellInstance.value = new ContentSelectionCell()

  // Hydrate filter from props
  if (props.cell?.initial_data?.content_type_id) {
    localContentTypeFilter.value = props.cell.initial_data.content_type_id
  }

  // Load initial content list
  loadContents()
})

// ── Data Loading ───────────────────────────────────────────────────────
async function loadContents(): Promise<void> {
  if (!cellInstance.value) return

  isLoading.value = true
  localError.value = null
  selectionConfirmed.value = false

  try {
    const input: Record<string, any> = {
      action: 'list',
      limit: localLimit.value,
      offset: localOffset.value
    }

    // Apply content_type_id filter
    if (localContentTypeFilter.value) {
      input.content_type_id = localContentTypeFilter.value
    }

    // Apply filename search (passed as filter)
    if (localSearchQuery.value.trim()) {
      input.filters = {
        ...(input.filters || {}),
        filename: localSearchQuery.value.trim()
      }
    }

    const result: CellResult = await cellInstance.value.execute(input)

    if (result.success && result.output) {
      localContents.value = result.output.contents || []
      localTotal.value = result.output.total || 0
      localLimit.value = result.output.limit || 20
      localOffset.value = result.output.offset || 0
    } else {
      localError.value = result.error || 'Failed to load content list'
      localContents.value = []
      localTotal.value = 0
    }
  } catch (error: any) {
    localError.value = error.message || 'An unexpected error occurred'
    localContents.value = []
    localTotal.value = 0
  } finally {
    isLoading.value = false
  }
}

// ── Event Handlers ─────────────────────────────────────────────────────
function handleFilterChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  localContentTypeFilter.value = target.value
  localOffset.value = 0
  localSelectedContent.value = null
  loadContents()
}

function handleSearchInput(): void {
  // Debounce search to avoid excessive API calls
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    localOffset.value = 0
    localSelectedContent.value = null
    loadContents()
  }, 300)
}

function handlePageChange(direction: 'prev' | 'next'): void {
  if (direction === 'prev' && localOffset.value > 0) {
    localOffset.value = Math.max(0, localOffset.value - localLimit.value)
  } else if (direction === 'next' && localOffset.value + localLimit.value < localTotal.value) {
    localOffset.value += localLimit.value
  }
  loadContents()
}

function handleSelect(content: ContentItem): void {
  // Toggle selection if same item clicked
  if (localSelectedContent.value?.id === content.id) {
    localSelectedContent.value = null
    return
  }
  localSelectedContent.value = content
  selectionConfirmed.value = false
}

function clearSelection(): void {
  localSelectedContent.value = null
  selectionConfirmed.value = false
  selectionResult.value = {}
}

function confirmSelection(): void {
  if (!localSelectedContent.value) return

  const selected = localSelectedContent.value
  const result = {
    selected_content_id: selected.id,
    selected_filename: selected.filename,
    selected_name: selected.fragments?.name || selected.filename,
    selected_content_type_id: selected.content_type_id || selected.content_type || '',
    selected_size_bytes: selected.size_bytes || 0,
    selected_data_ref: selected.data_ref || ''
  }

  selectionResult.value = result
  selectionConfirmed.value = true

  // Emit to parent so it can use the selection
  emit('update:cell', {
    ...props.cell,
    initial_data: {
      ...props.cell.initial_data,
      ...result
    }
  })
  emit('execute')
}

// ── Helpers ────────────────────────────────────────────────────────────
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)
  return `${size} ${units[i]}`
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

function contentTypeBadgeClass(typeId?: string): string {
  switch (typeId) {
    case 'image-png':
      return 'bg-blue-100 text-blue-800'
    case 'vector-svg':
      return 'bg-purple-100 text-purple-800'
    case '3d-glb':
      return 'bg-green-100 text-green-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}
</script>

<style scoped>
.content-selection-cell {
  min-height: 200px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
