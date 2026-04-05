/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-28",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<script setup lang="ts">
/**
 * GLB File Uploader Component
 * 
 * Handles direct upload of GLB files for instant preview.
 * Creates blob URL for immediate TresJS rendering without backend processing.
 * 
 * @component
 */
import { ref } from 'vue'
import { createLogger } from '@/utils/logger'

const logger = createLogger('component:glb-file-uploader')

interface Props {
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
})

const emit = defineEmits<{
  (e: 'upload', file: File, blobUrl: string): void
  (e: 'error', error: string): void
}>()

const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

/**
 * Handle file selection or drop
 */
const handleFile = (file: File) => {
  if (!file.name.toLowerCase().endsWith('.glb')) {
    const error = 'Please upload a valid GLB file'
    logger.error(error)
    emit('error', error)
    return
  }

  logger.info(`GLB file selected: ${file.name} (${file.size} bytes)`)

  try {
    // Create blob URL for instant preview
    const blobUrl = URL.createObjectURL(file)
    logger.debug('Created blob URL for GLB file')
    
    emit('upload', file, blobUrl)
  } catch (err: any) {
    const error = `Failed to process GLB file: ${err.message}`
    logger.error(error, err)
    emit('error', error)
  }
}

/**
 * Handle file input change
 */
const handleFileInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (file) {
    handleFile(file)
  }

  // Reset input to allow same file selection
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

/**
 * Handle drag enter
 */
const handleDragEnter = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = true
}

/**
 * Handle drag leave
 */
const handleDragLeave = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false
}

/**
 * Handle drag over
 */
const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
}

/**
 * Handle file drop
 */
const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDragging.value = false

  const file = event.dataTransfer?.files?.[0]
  if (file) {
    handleFile(file)
  }
}

/**
 * Trigger file input click
 */
const triggerFileInput = () => {
  if (!props.disabled && fileInput.value) {
    fileInput.value.click()
  }
}
</script>

<template>
  <div class="glb-file-uploader">
    <label class="block text-sm font-medium mb-2 text-text-primary dark:text-text-primary-dark">
      Upload GLB Model
    </label>

    <!-- Drop Zone -->
    <div
      :class="[
        'drop-zone relative p-8 rounded-lg border-2 border-dashed transition-all duration-200',
        'flex flex-col items-center justify-center cursor-pointer',
        isDragging
          ? 'border-primary dark:border-primary-light bg-primary/10 dark:bg-primary-light/10'
          : 'border-border dark:border-border-dark bg-surface dark:bg-surface-dark hover:border-primary/50 dark:hover:border-primary-light/50',
        disabled && 'opacity-50 cursor-not-allowed'
      ]"
      @dragenter="handleDragEnter"
      @dragleave="handleDragLeave"
      @dragover="handleDragOver"
      @drop="handleDrop"
      @click="triggerFileInput"
    >
      <!-- Icon -->
      <div class="mb-3">
        <svg
          class="w-12 h-12 text-text-secondary dark:text-text-secondary-dark"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
      </div>

      <!-- Text -->
      <div class="text-center">
        <p class="text-text-primary dark:text-text-primary-dark font-medium mb-1">
          <span v-if="isDragging">Drop GLB file here</span>
          <span v-else>Drop GLB file or click to browse</span>
        </p>
        <p class="text-sm text-text-secondary dark:text-text-secondary-dark">
          Supported format: .glb (GLTF Binary)
        </p>
      </div>

      <!-- Hidden File Input -->
      <input
        ref="fileInput"
        type="file"
        accept=".glb,model/gltf-binary"
        class="hidden"
        :disabled="disabled"
        @change="handleFileInput"
      />
    </div>

    <!-- Info Note -->
    <p class="text-xs text-text-secondary dark:text-text-secondary-dark mt-2">
      💡 <strong>Tip:</strong> Upload your own GLB models for instant preview in the 3D viewport
    </p>
  </div>
</template>

<style scoped>
.drop-zone {
  min-height: 200px;
}

.drop-zone:not(.disabled) {
  cursor: pointer;
}
</style>
