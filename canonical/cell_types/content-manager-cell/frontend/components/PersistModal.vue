/**
 * @file PersistModal.vue
 * @description Modal component for persisting generated assets
 * 
 * This component provides a user-friendly interface for naming, tagging,
 * and saving generated assets (PNG images) to persistent storage via
 * ContentManagerCell.
 * 
 * Features:
 * - Asset preview with metadata (dimensions, size, timestamp)
 * - Form inputs for name, description, tags
 * - Public/private visibility toggle
 * - Integration with ContentManagerCell.execute() for persistence
 * 
 * Part of PNG Generator persistence feature implementation
 */
<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="persist-modal-overlay"
      @click.self="handleCancel"
    >
      <div class="persist-modal-container">
        <!-- Modal Header -->
        <div class="modal-header">
          <h2 class="text-xl font-semibold text-text-primary dark:text-text-primary-dark">
            Persist Generated Asset
          </h2>
          <button
            @click="handleCancel"
            class="close-btn text-text-secondary dark:text-text-secondary-dark hover:text-text-primary dark:hover:text-text-primary-dark"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <!-- Asset Preview Section -->
        <div class="asset-preview">
          <div
            v-if="assetData?.image_data || assetData?.generatedPng"
            class="preview-image-container"
          >
            <img
              :src="assetData.image_data || assetData.generatedPng"
              alt="Asset preview"
              class="preview-image"
            />
          </div>
          <div class="asset-metadata">
            <p class="metadata-item">
              <strong>Dimensions:</strong>
              {{ assetData?.width || 'N/A' }}×{{ assetData?.height || 'N/A' }}px
            </p>
            <p class="metadata-item">
              <strong>Size:</strong>
              {{ formatFileSize(assetData?.file_size) }}
            </p>
            <p class="metadata-item">
              <strong>Generated:</strong>
              {{ formatDate(assetData?.generation_timestamp || assetData?.timestamp) }}
            </p>
            <p v-if="assetData?.prompt" class="metadata-item">
              <strong>Prompt:</strong>
              <span class="text-sm italic">{{ truncateText(assetData.prompt, 100) }}</span>
            </p>
          </div>
        </div>

        <!-- Form Section -->
        <div class="form-section">
          <div class="form-group">
            <label class="form-label">
              Asset Name *
            </label>
            <input
              v-model="formData.name"
              type="text"
              placeholder="e.g., Character Portrait v2"
              required
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              Description
            </label>
            <textarea
              v-model="formData.description"
              placeholder="Brief description of the asset..."
              rows="3"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              Tags
            </label>
            <input
              v-model="formData.tags"
              type="text"
              placeholder="comma, separated, tags"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="formData.make_public"
                class="checkbox-input"
              />
              <span>Make asset public/shareable</span>
            </label>
          </div>
        </div>

        <!-- Actions Section -->
        <div class="modal-actions">
          <button
            @click="handleCancel"
            class="btn-secondary"
            :disabled="isPersisting"
          >
            Cancel
          </button>
          <button
            @click="handlePersist"
            class="btn-primary"
            :disabled="!formData.name || isPersisting"
          >
            <svg
              v-if="isPersisting"
              class="animate-spin h-4 w-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              />
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>
              {{ isPersisting ? 'Persisting...' : 'Persist Asset' }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, type PropType } from 'vue'
import { ContentManagerCell } from '../ContentManagerCell'
import type { CellResult } from '@/types/BaseCell'
import { createLogger } from '@/utils/logger'
import authService from '@/services/authService'

const log = createLogger('components:PersistModal')

interface Props {
  assetData: Record<string, any>
  isVisible?: boolean
  onConfirm?: (result: CellResult) => void
  onCancel?: () => void
}

const props = withDefaults(defineProps<Props>(), {
  isVisible: true
})

const emit = defineEmits<{
  (e: 'confirm', result: CellResult): void
  (e: 'cancel'): void
}>()

interface FormData {
  name: string
  description: string
  tags: string
  make_public: boolean
}

const formData = ref<FormData>({
  name: '',
  description: '',
  tags: '',
  make_public: false
})

const isPersisting = ref(false)

/**
 * Handle asset persistence
 */
async function handlePersist(): Promise<void> {
  if (!formData.value.name.trim()) {
    log.warn('Asset name is required')
    return
  }

  isPersisting.value = true
  log.info('Persisting asset', { name: formData.value.name })

  try {
    const contentManager = new ContentManagerCell()

    // Set authentication token for API calls
    const token = authService.getToken()
    if (token) {
      contentManager.setAuthToken(token)
      log.debug('Auth token set for content persistence')
    } else {
      log.warn('No auth token found for content persistence')
    }

    // Parse tags from comma-separated string
    const tags = formData.value.tags
      .split(',')
      .map(t => t.trim())
      .filter(t => t.length > 0)

    // Build persistence request
    const result = await contentManager.execute({
      action: 'persist',
      content_type_id: 'image-png',
      filename: `${formData.value.name}.png`,
      binary: props.assetData.image_data || props.assetData.generatedPng,
      metadata: {
        description: formData.value.description,
        tags,
        public: formData.value.make_public,
        generated_at: props.assetData.generation_timestamp || props.assetData.timestamp,
        generation_params: props.assetData.generation_params || props.assetData.generationParams,
        prompt: props.assetData.prompt,
        dimensions: {
          width: props.assetData.width,
          height: props.assetData.height
        }
      }
    })

    if (result.success) {
      log.info('Asset persisted successfully', { result })
      if (props.onConfirm) {
        props.onConfirm(result)
      }
      emit('confirm', result)
    } else {
      throw new Error(result.error || 'Persistence failed')
    }
  } catch (error: any) {
    log.error('Failed to persist asset', { error: error.message })
    alert(`Failed to persist asset: ${error.message}`)
  } finally {
    isPersisting.value = false
  }
}

/**
 * Handle cancel action
 */
function handleCancel(): void {
  if (!isPersisting.value) {
    log.debug('Persist modal cancelled')
    if (props.onCancel) {
      props.onCancel()
    }
    emit('cancel')
  }
}

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes?: number): string {
  if (!bytes) return 'N/A'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

/**
 * Format timestamp as localized date string
 */
function formatDate(timestamp?: number): string {
  if (!timestamp) return 'N/A'
  return new Date(timestamp).toLocaleString()
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>

<style scoped>
.persist-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}

.persist-modal-container {
  background: var(--color-surface, white);
  border-radius: 8px;
  padding: 24px;
  max-width: 600px;
  width: 90%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

@media (prefers-color-scheme: dark) {
  .persist-modal-container {
    background: var(--color-surface-dark, #1f2937);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.modal-header h2 {
  margin: 0;
  font-size: 20px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.close-btn:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

@media (prefers-color-scheme: dark) {
  .close-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
  }
}

.asset-preview {
  margin-bottom: 24px;
}

.preview-image-container {
  width: 100%;
  max-height: 300px;
  background: var(--color-surface-light, #f9fafb);
  border-radius: 6px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

@media (prefers-color-scheme: dark) {
  .preview-image-container {
    background: var(--color-surface-dark-light, #374151);
  }
}

.preview-image {
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  border-radius: 4px;
}

.asset-metadata {
  background: var(--color-surface-light, #f5f5f5);
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
}

@media (prefers-color-scheme: dark) {
  .asset-metadata {
    background: var(--color-surface-dark-light, #374151);
    color: var(--color-text-secondary-dark, #9ca3af);
  }
}

.metadata-item {
  margin: 6px 0;
  line-height: 1.5;
}

.metadata-item strong {
  color: var(--color-text-primary, #333);
}

@media (prefers-color-scheme: dark) {
  .metadata-item strong {
    color: var(--color-text-primary-dark, #e5e7eb);
  }
}

.form-section {
  margin-bottom: 24px;
}

.form-group {
  margin-bottom: 16px;
}

.form-label {
  display: block;
  font-weight: 500;
  margin-bottom: 6px;
  font-size: 14px;
  color: var(--color-text-primary, #333);
}

@media (prefers-color-scheme: dark) {
  .form-label {
    color: var(--color-text-primary-dark, #e5e7eb);
  }
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  background: var(--color-surface, white);
  color: var(--color-text-primary, #333);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-primary, #0066cc);
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
}

@media (prefers-color-scheme: dark) {
  .form-input {
    background: var(--color-surface-dark, #1f2937);
    border-color: var(--color-border-dark, #4b5563);
    color: var(--color-text-primary-dark, #e5e7eb);
  }
  
  .form-input:focus {
    border-color: var(--color-primary-light, #3b82f6);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  }
}

.form-input textarea {
  resize: vertical;
  min-height: 80px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-primary, #333);
}

@media (prefers-color-scheme: dark) {
  .checkbox-label {
    color: var(--color-text-primary-dark, #e5e7eb);
  }
}

.checkbox-input {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: var(--color-primary, #0066cc);
}

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}

.btn-primary,
.btn-secondary {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-primary {
  background: var(--color-primary, #0066cc);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover, #0052a3);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.3);
}

.btn-primary:disabled {
  background: var(--color-border, #ccc);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@media (prefers-color-scheme: dark) {
  .btn-primary {
    background: var(--color-primary-dark, #3b82f6);
  }
  
  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover, #2563eb);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
  }
  
  .btn-primary:disabled {
    background: var(--color-border-dark, #4b5563);
  }
}

.btn-secondary {
  background: var(--color-surface-light, #f0f0f0);
  color: var(--color-text-primary, #333);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-surface-hover, #e0e0e0);
}

@media (prefers-color-scheme: dark) {
  .btn-secondary {
    background: var(--color-surface-dark-light, #374151);
    color: var(--color-text-primary-dark, #e5e7eb);
  }
  
  .btn-secondary:hover:not(:disabled) {
    background: var(--color-surface-dark-hover, #4b5563);
  }
}
</style>
