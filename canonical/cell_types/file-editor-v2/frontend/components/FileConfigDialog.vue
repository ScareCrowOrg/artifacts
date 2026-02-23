/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-26",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-26",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-17",
 *   "console_calls_found": 4,
 *   "console_calls_migrated": 4,
 *   "migration_rate": 100,
 *   "logger_namespace": "components:file-config",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-4"
      @click.self="handleCancel"
    >
      <div
        class="bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        @click.stop
      >
        <!-- Header -->
        <div class="flex justify-between items-center p-6 border-b border-border dark:border-border-dark">
          <h3 class="text-xl font-semibold text-text-primary dark:text-text-primary-dark m-0">
            {{ $t('fileConfigDialog.title') }}
          </h3>
          <button
            class="p-2 text-text-secondary dark:text-text-secondary-dark hover:text-error hover:bg-error/10 rounded transition-colors"
            type="button"
            :title="$t('common.close')"
            @click="handleCancel"
          >
            ✕
          </button>
        </div>

        <!-- Body -->
        <div class="p-6 space-y-6">
          <!-- Filename Input -->
          <div>
            <label
              for="filename-input"
              class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
            >
              {{ $t('fileConfigDialog.filenameLabel') }}
              <span class="text-error">*</span>
            </label>
            <input
              id="filename-input"
              v-model="filename"
              type="text"
              :placeholder="$t('fileConfigDialog.filenamePlaceholder')"
              class="w-full px-3 py-2 border border-border dark:border-border-dark rounded-md bg-surface dark:bg-surface-dark text-text-primary dark:text-text-primary-dark placeholder:text-text-secondary dark:placeholder:text-text-secondary-dark focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              :class="{ 'border-error focus:ring-error': filenameError }"
              @input="validateFilename"
            />
            <p
              v-if="filenameError"
              class="mt-1 text-sm text-error"
            >
              {{ filenameError }}
            </p>
          </div>

          <!-- Directory Picker -->
          <div>
            <label
              for="directory-picker"
              class="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-2"
            >
              {{ $t('fileConfigDialog.directoryLabel') }}
              <span class="text-error">*</span>
            </label>
            <DirectoryPicker
              id="directory-picker"
              v-model="directory"
              :placeholder="$t('fileConfigDialog.directoryPlaceholder')"
            />
            <p class="mt-1 text-xs text-text-secondary dark:text-text-secondary-dark">
              {{ $t('fileConfigDialog.directoryHint') }}
            </p>
          </div>

          <!-- Full Path Preview -->
          <div
            v-if="fullPath"
            class="p-4 bg-primary/5 border border-primary/20 rounded-md"
          >
            <p class="text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
              {{ $t('fileConfigDialog.fullPathLabel') }}
            </p>
            <code class="text-sm font-mono text-primary dark:text-primary-light break-all">
              {{ fullPath }}
            </code>
          </div>
        </div>

        <!-- Footer -->
        <div class="flex justify-end gap-3 p-6 border-t border-border dark:border-border-dark">
          <button
            class="px-4 py-2 text-sm font-medium text-text-primary dark:text-text-primary-dark bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-md hover:bg-surface-hover dark:hover:bg-surface-dark transition-colors"
            type="button"
            @click="handleCancel"
          >
            {{ $t('common.cancel') }}
          </button>
          <button
            class="px-4 py-2 text-sm font-medium text-white bg-success rounded-md hover:bg-success/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            type="button"
            :disabled="!canConfirm"
            @click="handleConfirm"
          >
            {{ $t('fileConfigDialog.confirmButton') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { createLogger } from '@/utils/logger'
import DirectoryPicker from './DirectoryPicker.vue'

const { t: $t } = useI18n()
const log = createLogger('components:file-config')

/**
 * FileConfigDialog Component
 * 
 * A modal dialog for configuring file name and directory path.
 * Can be used for both new file creation and editing existing file paths.
 * Provides directory selection with DirectoryPicker component.
 */

interface Props {
  /** Whether the dialog is open */
  isOpen: boolean
  /** Initial filename (with extension) */
  initialFilename?: string
  /** Initial directory path */
  initialDirectory?: string
}

interface EmitEvents {
  /** Emitted when dialog is closed */
  'update:isOpen': [value: boolean]
  /** Emitted when configuration is confirmed */
  'confirm': [data: { filename: string; directory: string }]
}

const props = withDefaults(defineProps<Props>(), {
  initialFilename: 'novo_arquivo.md',
  initialDirectory: 'docs'
})

const emit = defineEmits<EmitEvents>()

// State
const filename = ref<string>(props.initialFilename)
const directory = ref<string>(props.initialDirectory)
const filenameError = ref<string>('')

// Computed
const fullPath = computed<string>(() => {
  if (!filename.value) return ''
  
  const name = filename.value.trim()
  const dir = directory.value.trim()
  
  // Build full path
  if (dir) {
    return `${dir}/${name}`
  }
  return name
})

const canConfirm = computed<boolean>(() => {
  return !!(
    filename.value.trim() &&
    !filenameError.value &&
    directory.value.trim()
  )
})

// Methods
function validateFilename(): void {
  const name = filename.value.trim()
  
  if (!name) {
    filenameError.value = $t('fileConfigDialog.filenameRequired')
    return
  }
  
  // Check for invalid characters
  const invalidChars = /[<>:"|?*\x00-\x1F]/g
  if (invalidChars.test(name)) {
    filenameError.value = $t('fileConfigDialog.filenameInvalidChars')
    return
  }
  
  // Check for reserved names (Windows)
  const reserved = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i
  if (reserved.test(name.split('.')[0])) {
    filenameError.value = $t('fileConfigDialog.filenameReserved')
    return
  }
  
  filenameError.value = ''
}

function handleCancel(): void {
  emit('update:isOpen', false)
  resetForm()
}

function handleConfirm(): void {
  if (!canConfirm.value) return
  
  const name = filename.value.trim()
  const dir = directory.value.trim()
  
  log.debug('Confirm clicked', {
    filename: name,
    directory: dir,
    fullPath: fullPath.value
  })
  
  emit('confirm', {
    filename: name,
    directory: dir
  })
  
  log.debug('Emitted confirm event')
  
  emit('update:isOpen', false)
}

function resetForm(): void {
  filename.value = props.initialFilename
  directory.value = props.initialDirectory
  filenameError.value = ''
}

// Watch for dialog open/close and prop changes
watch(() => props.isOpen, (newValue) => {
  if (newValue) {
    // Reset form with current prop values when dialog opens
    log.debug('Dialog opened, resetting form', {
      initialFilename: props.initialFilename,
      initialDirectory: props.initialDirectory
    })
    filename.value = props.initialFilename
    directory.value = props.initialDirectory
    filenameError.value = ''
  }
})

watch(() => props.initialFilename, (newValue) => {
  if (props.isOpen) {
    filename.value = newValue
  }
})

watch(() => props.initialDirectory, (newValue) => {
  if (props.isOpen) {
    directory.value = newValue
  }
})

// Watch directory changes for debugging
watch(directory, (newValue, oldValue) => {
  log.debug('Directory value changed', {
    from: oldValue,
    to: newValue,
    fullPath: fullPath.value
  })
})
</script>

<style scoped>
/* No custom styles needed - using Tailwind utilities and design system */
</style>
