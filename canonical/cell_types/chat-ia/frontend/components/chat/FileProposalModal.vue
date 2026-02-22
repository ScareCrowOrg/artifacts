/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-14",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-14",
 *   "theme_compliance": 100,
 *   "dark_mode_support": "full",
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-12-28",
 *   "console_calls_found": 13,
 *   "console_calls_migrated": 13,
 *   "migration_rate": 100,
 *   "logger_namespace": "chat:file-proposal",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <div
    v-if="isVisible"
    class="file-proposal-modal fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
    @click.self="handleCancel"
  >
    <div class="modal-content bg-surface dark:bg-surface-dark rounded-lg shadow-xl border border-border dark:border-border-dark max-w-4xl w-full mx-4 max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="modal-header px-6 py-4 border-b border-border dark:border-border-dark">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-xl font-semibold text-text-primary dark:text-text-primary-dark">
              {{ isUpdate ? t('fileProposal.updateTitle') : t('fileProposal.createTitle') }}
            </h2>
            <p class="text-sm text-text-secondary dark:text-text-secondary-dark mt-1">
              {{ filePath }}
            </p>
          </div>
          <button
            class="text-text-secondary dark:text-text-secondary-dark hover:text-text-primary dark:hover:text-text-primary-dark"
            :aria-label="t('fileProposal.close')"
            @click="handleCancel"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      
      <!-- Description -->
      <div v-if="description" class="px-6 py-3 bg-primary/5 dark:bg-primary-dark/5 border-b border-border dark:border-border-dark">
        <p class="text-sm text-text-primary dark:text-text-primary-dark">
          <span class="font-semibold">{{ t('fileProposal.reason') }}:</span> {{ description }}
        </p>
      </div>
      
      <!-- Content -->
      <div class="modal-body px-6 py-4 overflow-y-auto flex-1">
        <!-- Show diff for updates -->
        <div v-if="isUpdate && diff">
          <DiffViewer :diff="diff" />
        </div>
        
        <!-- Show full content for new files -->
        <div v-else-if="!isUpdate" class="new-file-content">
          <div class="mb-3">
            <span class="text-sm font-semibold text-text-primary dark:text-text-primary-dark">
              {{ t('fileProposal.newFileContent') }}:
            </span>
          </div>
          <div class="bg-surface-hover dark:bg-surface-hover-dark rounded-lg border border-border dark:border-border-dark overflow-hidden">
            <pre class="p-4 overflow-x-auto overflow-y-auto max-h-[400px] text-sm font-mono text-text-primary dark:text-text-primary-dark"><code class="whitespace-pre-wrap break-words">{{ content }}</code></pre>
          </div>
        </div>
      </div>
      
      <!-- Footer with actions -->
      <div class="modal-footer px-6 py-4 border-t border-border dark:border-border-dark bg-surface-hover dark:bg-surface-hover-dark">
        <div class="flex justify-between items-center">
          <div class="text-xs text-text-secondary dark:text-text-secondary-dark">
            {{ t('fileProposal.hint') }}
          </div>
          <div class="flex gap-3">
            <button
              :disabled="processing"
              class="px-4 py-2 rounded-md text-sm font-medium border border-border dark:border-border-dark text-text-primary dark:text-text-primary-dark hover:bg-surface dark:hover:bg-surface-dark transition-colors"
              @click="handleCancel"
            >
              {{ t('fileProposal.reject') }}
            </button>
            <button
              :disabled="processing"
              class="px-4 py-2 rounded-md text-sm font-medium bg-success dark:bg-success-dark text-white hover:bg-success/90 dark:hover:bg-success-dark/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              @click="handleAccept"
            >
              <span v-if="processing" class="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              {{ t('fileProposal.accept') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import DiffViewer from './DiffViewer.vue'
import { computeDiff } from '@/utils/diffUtils'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:file-proposal')
const { t } = useI18n()

const props = defineProps({
  /**
   * Whether modal is visible
   */
  isVisible: {
    type: Boolean,
    default: false
  },
  
  /**
   * Type of proposal: 'update' or 'create'
   */
  type: {
    type: String,
    required: true,
    validator: (v) => ['update', 'create'].includes(v)
  },
  
  /**
   * File path
   */
  filePath: {
    type: String,
    required: true
  },
  
  /**
   * Description of the change
   */
  description: {
    type: String,
    default: ''
  },
  
  /**
   * Original content (for updates)
   */
  originalContent: {
    type: String,
    default: ''
  },
  
  /**
   * New/updated content
   */
  content: {
    type: String,
    required: true
  },
  
  /**
   * Starting line for snippet updates (1-indexed)
   */
  startLine: {
    type: Number,
    default: undefined
  },
  
  /**
   * Ending line for snippet updates (1-indexed)
   */
  endLine: {
    type: Number,
    default: undefined
  }
})

const emit = defineEmits(['accept', 'cancel', 'close'])

const processing = ref(false)

const isUpdate = computed(() => {
  const result = props.type === 'update'
  log.debug('isUpdate computed', {
    type: props.type,
    isUpdate: result
  })
  return result
})

const diff = computed(() => {
  log.debug('Computing diff', {
    isUpdate: isUpdate.value,
    hasOriginalContent: !!props.originalContent,
    originalContentLength: props.originalContent?.length || 0,
    hasContent: !!props.content,
    contentLength: props.content?.length || 0
  })
  
  if (isUpdate.value && props.originalContent) {
    const diffResult = computeDiff(props.originalContent, props.content)
    
    log.debug('Diff computed', {
      hasDiff: !!diffResult,
      diffLength: diffResult?.length || 0,
      additions: diffResult?.filter(d => d.type === 'addition').length || 0,
      deletions: diffResult?.filter(d => d.type === 'deletion').length || 0,
      unchanged: diffResult?.filter(d => d.type === 'unchanged').length || 0
    })
    
    return diffResult
  }
  
  log.debug('No diff computed (not update or missing content)')
  return null
})

// Enhanced logging: Watch props changes
watchEffect(() => {
  if (props.isVisible) {
    log.debug('Modal visibility changed to visible, props', {
      isVisible: props.isVisible,
      type: props.type,
      filePath: props.filePath,
      hasDescription: !!props.description,
      descriptionLength: props.description?.length || 0,
      hasOriginalContent: !!props.originalContent,
      originalContentLength: props.originalContent?.length || 0,
      hasContent: !!props.content,
      contentLength: props.content?.length || 0
    })
  }
})

async function handleAccept() {
  log.debug('Accept button clicked', {
    type: props.type,
    filePath: props.filePath,
    hasStartLine: props.startLine !== undefined,
    hasEndLine: props.endLine !== undefined,
    startLine: props.startLine,
    endLine: props.endLine,
    timestamp: new Date().toISOString()
  })
  
  processing.value = true
  
  try {
    const proposalData = {
      type: props.type,
      filePath: props.filePath,
      content: props.content,
      originalContent: props.originalContent,
      description: props.description
    }
    
    // Include line numbers and snippet flag if available (snippet mode)
    if (props.startLine !== undefined && props.endLine !== undefined) {
      proposalData.startLine = props.startLine
      proposalData.endLine = props.endLine
      proposalData.isSnippet = true
    }
    
    log.debug('Emitting accept event with proposal data', {
      type: proposalData.type,
      filePath: proposalData.filePath,
      hasContent: !!proposalData.content,
      contentLength: proposalData.content?.length || 0,
      hasOriginalContent: !!proposalData.originalContent,
      originalContentLength: proposalData.originalContent?.length || 0,
      isSnippet: proposalData.isSnippet || false,
      startLine: proposalData.startLine,
      endLine: proposalData.endLine
    })
    
    await emit('accept', proposalData)
    
    log.debug('Accept event completed successfully')
  } catch (error) {
    log.error('Accept event failed', error)
    throw error
  } finally {
    processing.value = false
    log.debug('Processing state reset')
  }
}

function handleCancel() {
  log.debug('Cancel/Close initiated', {
    processing: processing.value,
    filePath: props.filePath
  })
  
  if (!processing.value) {
    log.debug('Emitting cancel and close events')
    emit('cancel')
    emit('close')
  } else {
    log.debug('Cancel blocked - still processing')
  }
}
</script>

<style scoped>
.modal-content {
  animation: modalFadeIn 0.2s ease-out;
}

@keyframes modalFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
