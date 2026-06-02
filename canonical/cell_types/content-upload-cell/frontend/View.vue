<template>
  <div class="content-upload-cell bg-surface border border-border rounded-lg p-4">
    <!-- Header -->
    <div class="flex items-center gap-2 mb-4">
      <svg class="w-6 h-6 text-primary flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12" />
      </svg>
      <h3 class="text-lg font-semibold">Content Upload</h3>
    </div>

    <!-- File Input Area -->
    <div class="mb-4">
      <div
        class="flex flex-col items-center justify-center gap-2 p-6 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary/50 hover:bg-surface-alt transition-colors"
        :class="{ 'opacity-50 pointer-events-none': isUploading }"
        @click="triggerFileInput"
        @dragover.prevent="isDragOver = true"
        @dragleave="isDragOver = false"
        @drop.prevent="handleDrop"
      >
        <svg v-if="!selectedFile" class="w-10 h-10 text-text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <svg v-else class="w-10 h-10 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>

        <p v-if="!selectedFile" class="text-sm text-text-secondary">
          Click to select or drag a file here
        </p>
        <p v-else class="text-sm font-medium text-text-primary">
          {{ selectedFile.name }}
        </p>
        <p v-if="selectedFile" class="text-xs text-text-secondary">
          {{ formatFileSize(selectedFile.size) }}
        </p>

        <input
          ref="fileInputRef"
          type="file"
          class="hidden"
          :accept="acceptTypes"
          :multiple="allowMultiple"
          @change="handleFileSelected"
        />
      </div>
    </div>

    <!-- Upload & Persist Button -->
    <button
      class="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-md hover:bg-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      :disabled="!selectedFile || isUploading"
      @click="uploadAndPersist"
    >
      <svg v-if="!isUploading" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5-5m0 0l5 5m-5-5v12" />
      </svg>
      <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {{ isUploading ? 'Uploading...' : 'Upload & Persist' }}
    </button>

    <!-- Validation Errors -->
    <div v-if="validationErrors.length > 0" class="mt-3 p-3 bg-error/10 border border-error/30 rounded text-sm">
      <p class="font-medium text-error mb-1">Validation Error</p>
      <ul class="list-disc list-inside text-error/80 space-y-0.5">
        <li v-for="(err, index) in validationErrors" :key="index">
          {{ err.message }}
        </li>
      </ul>
    </div>

    <!-- Backend Error -->
    <div v-if="backendError" class="mt-3 p-3 bg-error/10 border border-error/30 rounded text-error text-sm">
      <div class="flex items-start gap-2">
        <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>{{ backendError }}</span>
      </div>
    </div>

    <!-- Network Error -->
    <div v-if="networkError" class="mt-3 p-3 bg-error/10 border border-error/30 rounded text-error text-sm">
      <div class="flex items-start gap-2">
        <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728m-2.829-2.829a5 5 0 000-7.07m-4.243 4.243a1 1 0 010-1.414" />
        </svg>
        <span>{{ networkError }}</span>
      </div>
    </div>

    <!-- Result Display -->
    <div v-if="uploadResult" class="mt-3 p-3 bg-success/10 border border-success/30 rounded text-sm">
      <p class="font-medium text-success mb-2">Upload Successful</p>
      <div class="space-y-1 text-text-primary">
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[90px]">File:</span>
          <span class="truncate">{{ uploadResult.filename }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[90px]">Size:</span>
          <span>{{ formatFileSize(uploadResult.size_bytes) }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[90px]">Content ID:</span>
          <code class="text-xs bg-surface-alt px-1.5 py-0.5 rounded truncate">{{ uploadResult.content_id }}</code>
        </div>
        <div v-if="uploadResult.data_ref" class="flex items-center gap-2">
          <span class="font-medium text-text-secondary min-w-[90px]">Data Ref:</span>
          <code class="text-xs bg-surface-alt px-1.5 py-0.5 rounded truncate">{{ uploadResult.data_ref }}</code>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isUploading" class="mt-3 flex items-center justify-center gap-2 py-4 text-text-secondary text-sm">
      <div class="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      <span>Persisting file to storage...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, type Ref } from 'vue'
import { ContentUploadCell } from './ContentUploadCell'
import type { CellResult, ValidationError } from '@/types/BaseCell'

// ── Props ──────────────────────────────────────────────────────────────
interface Props {
  cell?: {
    id?: string
    initial_data?: {
      content_type_id?: string | null
      category?: string
      allowMultiple?: boolean
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
const cellInstance: Ref<ContentUploadCell | null> = ref(null)
const fileInputRef: Ref<HTMLInputElement | null> = ref(null)

const selectedFile: Ref<File | null> = ref(null)
const isDragOver: Ref<boolean> = ref(false)
const isUploading: Ref<boolean> = ref(false)

const validationErrors: Ref<ValidationError[]> = ref([])
const backendError: Ref<string | null> = ref(null)
const networkError: Ref<string | null> = ref(null)
const uploadResult: Ref<Record<string, any> | null> = ref(null)

const acceptTypes: Ref<string> = ref('*/*')
const allowMultiple: Ref<boolean> = ref(false)

// ── Hydration (Buffer Local Pattern Step 1) ────────────────────────────
onMounted(() => {
  cellInstance.value = new ContentUploadCell()

  // Hydrate from props
  if (props.cell?.initial_data) {
    if (props.cell.initial_data.content_type_id !== undefined) {
      acceptTypes.value = props.cell.initial_data.content_type_id === 'image-png'
        ? '.png'
        : props.cell.initial_data.content_type_id === 'vector-svg'
          ? '.svg'
          : props.cell.initial_data.content_type_id === '3d-glb'
            ? '.glb'
            : '*/*'
    }
    allowMultiple.value = props.cell.initial_data.allowMultiple || false
  }
})

// ── Event Handlers ─────────────────────────────────────────────────────
function triggerFileInput(): void {
  if (isUploading.value) return
  fileInputRef.value?.click()
}

function handleFileSelected(event: Event): void {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  selectedFile.value = target.files[0]

  // Clear previous states on new file selection
  clearErrors()
  uploadResult.value = null
}

function handleDrop(event: DragEvent): void {
  isDragOver.value = false
  if (!event.dataTransfer?.files || event.dataTransfer.files.length === 0) return
  selectedFile.value = event.dataTransfer.files[0]

  // Clear previous states
  clearErrors()
  uploadResult.value = null
}

function clearErrors(): void {
  validationErrors.value = []
  backendError.value = null
  networkError.value = null
}

async function uploadAndPersist(): Promise<void> {
  if (!selectedFile.value || !cellInstance.value) return

  // Reset state
  clearErrors()
  uploadResult.value = null
  isUploading.value = true

  try {
    // Read file as Base64
    const binary = await readFileAsBase64(selectedFile.value)

    // Determine assignee_id from cell instance or fallback
    const assigneeId = cellInstance.value.cell_instance?.assignee_id || 'default'

    // Execute persist
    const result: CellResult = await cellInstance.value.execute({
      filename: selectedFile.value.name,
      binary,
      assignee_id: assigneeId,
      content_type_id: props.cell?.initial_data?.content_type_id || null,
      origin_cell_id: props.cell?.id
    })

    if (result.success && result.output) {
      uploadResult.value = {
        content_id: result.output.content_id || result.output.id,
        data_ref: result.output.data_ref,
        filename: result.output.filename || selectedFile.value.name,
        size_bytes: result.output.size_bytes || selectedFile.value.size
      }

      // Emit update with content_id so parent can use it
      emit('update:cell', {
        ...props.cell,
        initial_data: {
          ...props.cell.initial_data,
          last_content_id: uploadResult.value.content_id,
          last_data_ref: uploadResult.value.data_ref
        }
      })
      emit('execute')
    } else {
      backendError.value = result.error || 'Upload failed - no error message'
    }
  } catch (error: any) {
    // Network/connection errors
    if (error.message?.includes('fetch') || error.name === 'TypeError') {
      networkError.value = 'Network error: Unable to reach server. Check your connection.'
    } else {
      backendError.value = error.message || 'An unexpected error occurred'
    }
  } finally {
    isUploading.value = false
  }
}

// ── Helpers ────────────────────────────────────────────────────────────
function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Extract base64 data from data URL (remove "data:*/*;base64," prefix)
      const base64 = result.includes(',') ? result.split(',')[1] : result
      resolve(base64)
    }
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsDataURL(file)
  })
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)
  return `${size} ${units[i]}`
}
</script>

<style scoped>
.content-upload-cell {
  min-height: 200px;
}

.hidden {
  display: none;
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
