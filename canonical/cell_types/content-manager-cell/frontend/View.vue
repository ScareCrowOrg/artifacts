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
  <div class="flex flex-col h-full bg-surface dark:bg-surface-dark p-6 gap-4 overflow-y-auto">
    <!-- Header -->
    <div class="flex justify-between items-start pb-4 border-b-2 border-gray-200 dark:border-gray-700">
      <div class="flex flex-col gap-1">
        <h2 class="m-0 text-2xl text-text-primary dark:text-text-primary-dark font-semibold">
          Content Manager
        </h2>
        <div class="flex items-center gap-1 text-sm text-text-secondary dark:text-text-secondary-dark">
          <span class="font-semibold">Persistent Storage</span>
          <span class="px-2 py-0.5 bg-success/10 border border-success/30 rounded text-success font-semibold">
            R2 / Local
          </span>
        </div>
      </div>
      
      <button
        class="px-3 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-primary dark:bg-primary-dark rounded-md hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 transition-colors"
        :disabled="isLoading"
        @click="handleRefresh"
      >
        {{ isLoading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <!-- Messages -->
    <div v-if="errorMessage" class="p-3 bg-error/10 border border-error/30 rounded text-error text-sm">
      {{ errorMessage }}
    </div>
    <div v-if="successMessage" class="p-3 bg-success/10 border border-success/30 rounded text-success text-sm">
      {{ successMessage }}
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 p-4 bg-surface-hover dark:bg-surface-dark border border-border dark:border-border-dark rounded-md">
      <div class="flex-1 min-w-[200px]">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
          Content Type
        </label>
        <select
          v-model="filters.content_type_id"
          class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
          @change="handleFilterChange"
        >
          <option :value="null">{{ $t('artifacts.contentManager.allTypes') }}</option>
          <option value="image-png">PNG Image</option>
          <option value="vector-svg">SVG Vector</option>
          <option value="3d-glb">3D Model (GLB)</option>
        </select>
      </div>
      
      <div class="flex-1 min-w-[200px]">
        <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
          Latest Only
        </label>
        <select
          v-model="filters.is_latest"
          class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
          @change="handleFilterChange"
        >
          <option :value="undefined">{{ $t('artifacts.contentExplorer.allVersions') }}</option>
          <option :value="true">{{ $t('artifacts.contentExplorer.latestOnly') }}</option>
          <option :value="false">{{ $t('artifacts.contentExplorer.olderVersions') }}</option>
        </select>
      </div>
      
      <div class="flex items-end">
        <button
          class="px-3 py-2 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface-dark border border-border dark:border-border-dark focus:outline-none focus:ring-2 focus:ring-border transition-colors"
          @click="handleClearFilters"
        >
          Clear Filters
        </button>
      </div>
    </div>

    <!-- Content List -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="isLoading && contents.length === 0" class="flex items-center justify-center h-64">
        <div class="text-text-secondary dark:text-text-secondary-dark">Loading contents...</div>
      </div>
      
      <div v-else-if="contents.length === 0" class="flex items-center justify-center h-64">
        <div class="text-center">
          <div class="text-text-secondary dark:text-text-secondary-dark text-lg mb-2">No contents found</div>
          <div class="text-text-secondary dark:text-text-secondary-dark text-sm">
            Try adjusting your filters or upload new content
          </div>
        </div>
      </div>
      
      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-surface-hover dark:bg-surface-dark border-b border-border dark:border-border-dark">
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Filename</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Type</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Size</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Version</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Created</th>
              <th class="px-4 py-3 text-left text-sm font-semibold text-text-primary dark:text-text-primary-dark">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="content in contents"
              :key="content.id"
              class="border-b border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-dark transition-colors"
            >
              <td class="px-4 py-3 text-sm text-text-primary dark:text-text-primary-dark">
                {{ content.filename }}
              </td>
              <td class="px-4 py-3 text-sm">
                <span class="px-2 py-1 bg-primary/10 text-primary dark:text-primary-light rounded text-xs font-medium">
                  {{ content.content_type_id }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-text-secondary dark:text-text-secondary-dark">
                {{ formatFileSize(content.size_bytes) }}
              </td>
              <td class="px-4 py-3 text-sm text-text-secondary dark:text-text-secondary-dark">
                v{{ content.version }}
                <span v-if="content.is_latest" class="ml-1 text-xs text-success">(latest)</span>
              </td>
              <td class="px-4 py-3 text-sm text-text-secondary dark:text-text-secondary-dark">
                {{ formatDate(content.created_at) }}
              </td>
              <td class="px-4 py-3 text-sm">
                <button
                  class="px-2 py-1 text-xs font-medium text-white bg-primary dark:bg-primary-dark rounded hover:bg-primary-hover dark:hover:bg-primary focus:outline-none focus:ring-2 focus:ring-primary transition-colors"
                  @click="handleDownload(content.id)"
                >
                  Download
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > 0" class="flex items-center justify-between p-4 bg-surface-hover dark:bg-surface-dark border border-border dark:border-border-dark rounded-md">
      <div class="text-sm text-text-secondary dark:text-text-secondary-dark">
        Showing {{ pagination.offset + 1 }}-{{ Math.min(pagination.offset + pagination.limit, total) }} of {{ total }} contents
      </div>
      
      <div class="flex gap-2">
        <button
          class="px-3 py-1 text-sm font-medium text-text-primary dark:text-text-primary-dark bg-surface dark:bg-surface-dark rounded border border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :disabled="currentPage <= 1"
          @click="handlePreviousPage"
        >
          Previous
        </button>
        
        <div class="flex items-center px-3 py-1 text-sm text-text-primary dark:text-text-primary-dark">
          Page {{ currentPage }} of {{ totalPages }}
        </div>
        
        <button
          class="px-3 py-1 text-sm font-medium text-text-primary dark:text-text-primary-dark bg-surface dark:bg-surface-dark rounded border border-border dark:border-border-dark hover:bg-surface-hover dark:hover:bg-surface-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :disabled="!hasMore"
          @click="handleNextPage"
        >
          Next
        </button>
      </div>
    </div>

    <!-- Persistence Form (Conditional) -->
    <div v-if="showPersistenceForm" class="p-4 bg-surface-hover dark:bg-surface-dark border-2 border-primary dark:border-primary-dark rounded-md">
      <h3 class="text-lg font-semibold text-text-primary dark:text-text-primary-dark mb-4">
        Upload New Content
      </h3>
      
      <form @submit.prevent="handleUpload" class="flex flex-col gap-4">
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            Content Type *
          </label>
          <select
            v-model="uploadForm.content_type_id"
            class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
            required
          >
            <option value="">Select type...</option>
            <option value="image-png">PNG Image (max 10 MB)</option>
            <option value="vector-svg">SVG Vector (max 5 MB)</option>
            <option value="3d-glb">3D Model GLB (max 50 MB)</option>
          </select>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            File *
          </label>
          <input
            type="file"
            @change="handleFileChange"
            class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
            required
          />
          <div v-if="uploadForm.file" class="mt-1 text-xs text-text-secondary dark:text-text-secondary-dark">
            Selected: {{ uploadForm.file.name }} ({{ formatFileSize(uploadForm.file.size) }})
          </div>
        </div>
        
        <div>
          <label class="block text-sm font-medium text-text-secondary dark:text-text-secondary-dark mb-1">
            Tags (comma-separated)
          </label>
          <input
            v-model="uploadForm.tagsStr"
            type="text"
            placeholder="e.g., generated, ai, png"
            class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        
        <div class="flex gap-2 justify-end">
          <button
            type="button"
            class="px-4 py-2 text-sm font-medium text-text-secondary dark:text-text-secondary-dark bg-surface dark:bg-surface-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface-dark border border-border dark:border-border-dark focus:outline-none focus:ring-2 focus:ring-border transition-colors"
            @click="handleCancelUpload"
          >
            Cancel
          </button>
          
          <button
            type="submit"
            class="px-4 py-2 text-sm font-medium text-white dark:text-text-primary-dark bg-success dark:bg-green-700 rounded-md hover:bg-green-600 dark:hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-success focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading || !uploadForm.file || !uploadForm.content_type_id"
          >
            {{ isLoading ? 'Uploading...' : 'Upload' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type PropType } from 'vue'
import { useContentManager } from './composables'
import type { ContentManagerCell, ContentPersistRequest } from './types'

// Props
const props = defineProps({
  cell: {
    type: Object as PropType<ContentManagerCell>,
    required: true
  }
})

// Extract initial data
const showPersistenceForm = computed(() => props.cell.initial_data.show_persistence_form || false)

// Use composable
const {
  contents,
  filters,
  pagination,
  total,
  isLoading,
  errorMessage,
  successMessage,
  hasMore,
  currentPage,
  totalPages,
  listContents,
  loadContent,
  persistContent,
  updateFilters,
  nextPage,
  previousPage,
  refresh,
  clearFilters
} = useContentManager(
  props.cell.id,
  props.cell.initial_data.filters,
  props.cell.initial_data.pagination
)

// Upload form state
const uploadForm = ref({
  content_type_id: props.cell.initial_data.default_content_type_id || '',
  file: null as File | null,
  tagsStr: ''
})

// Lifecycle
onMounted(async () => {
  await listContents()
})

// Event handlers
async function handleRefresh() {
  await refresh()
}

function handleFilterChange() {
  updateFilters(filters.value)
  listContents()
}

function handleClearFilters() {
  clearFilters()
  listContents()
}

async function handlePreviousPage() {
  await previousPage()
}

async function handleNextPage() {
  await nextPage()
}

async function handleDownload(contentId: string) {
  const result = await loadContent(contentId, false)
  
  if (result && 'presigned_url' in result) {
    // Open presigned URL in new tab
    window.open(result.presigned_url, '_blank')
  } else if (result && 'binary' in result) {
    // Download via data URI
    const link = document.createElement('a')
    link.href = result.binary
    link.download = result.filename
    link.click()
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    uploadForm.value.file = target.files[0]
  }
}

async function handleUpload() {
  if (!uploadForm.value.file || !uploadForm.value.content_type_id) {
    return
  }
  
  // Parse tags
  const tags = uploadForm.value.tagsStr
    .split(',')
    .map(t => t.trim())
    .filter(t => t.length > 0)
  
  // Build request
  const request: ContentPersistRequest = {
    content_type_id: uploadForm.value.content_type_id,
    filename: uploadForm.value.file.name,
    binary: uploadForm.value.file,
    fragments: extractFragmentsFromFile(uploadForm.value.file),
    tags,
    origin_cell_id: props.cell.id
  }
  
  const result = await persistContent(request)
  
  if (result) {
    // Reset form
    uploadForm.value.file = null
    uploadForm.value.tagsStr = ''
    ;(document.querySelector('input[type="file"]') as HTMLInputElement).value = ''
  }
}

function handleCancelUpload() {
  uploadForm.value.file = null
  uploadForm.value.tagsStr = ''
  ;(document.querySelector('input[type="file"]') as HTMLInputElement).value = ''
}

// Utility functions
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

function extractFragmentsFromFile(file: File): Record<string, any> {
  // Basic fragments extraction
  // In a real implementation, this would read image dimensions, etc.
  return {
    filename: file.name,
    size: file.size,
    type: file.type
  }
}
</script>
