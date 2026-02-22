/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2026-01-25",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2026-01-25",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues": 0,
 *   "logging_validated": true,
 *   "logging_validated_date": "2026-01-25",
 *   "logger_namespace": "chat:settings-modal",
 *   "validation_status": "excellent"
 * }
 */
<template>
  <!-- Modal overlay -->
  <div
    v-if="isOpen"
    class="fixed inset-0 bg-black/50 dark:bg-black/70 z-50 flex items-center justify-center p-4"
    @click="handleOverlayClick"
  >
    <!-- Modal container -->
    <div
      class="bg-surface dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col"
      @click.stop
    >
      <!-- Modal header -->
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-border dark:border-gray-700"
      >
        <div class="flex-grow min-w-0">
          <h2 class="text-xl font-bold text-text-primary dark:text-text-primary">
            {{ $t('chatSettingsModal.title') }}
          </h2>
          <p class="text-sm text-text-secondary dark:text-text-secondary mt-1">
            {{ $t('chatSettingsModal.subtitle') }}
          </p>
        </div>
        <button
          class="ml-4 p-2 hover:bg-surface-hover dark:hover:bg-gray-800 rounded-full transition-colors flex-shrink-0"
          :title="$t('chatSettingsModal.closeTooltip')"
          data-testid="close-settings-modal"
          @click="close"
        >
          <span class="text-2xl text-text-primary dark:text-text-primary">×</span>
        </button>
      </div>

      <!-- Modal content -->
      <div class="flex-grow overflow-y-auto px-6 py-4">
        <ChatSettingsPanel 
          :visible="true" 
          :chat="chat"
          @update:selected-model="handleModelUpdate"
          @update:enable-intention-classification="handleIntentionUpdate"
          @update:selected-collections="handleCollectionsUpdate"
        />
      </div>

      <!-- Modal footer -->
      <div class="px-6 py-4 border-t border-border dark:border-gray-700 flex justify-end">
        <button
          class="px-4 py-2 rounded-md text-sm font-medium bg-primary dark:bg-primary text-white hover:bg-primary/90 dark:hover:bg-primary/90 transition-colors"
          data-testid="close-settings-button"
          @click="close"
        >
          {{ $t('chatSettingsModal.closeButton') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { createLogger } from '@/utils/logger'
import ChatSettingsPanel from './ChatSettingsPanel.vue'

const log = createLogger('chat:settings-modal')

interface Props {
  isOpen: boolean
  chat: any // Using any for compatibility with ChatSettingsPanel which doesn't have typed props
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  'update:selected-model': [value: string]
  'update:enable-intention-classification': [value: boolean]
  'update:selected-collections': [value: string[]]
}>()

function close(): void {
  log.debug('Closing settings modal')
  emit('close')
}

function handleOverlayClick(): void {
  close()
}

function handleModelUpdate(value: string): void {
  emit('update:selected-model', value)
}

function handleIntentionUpdate(value: boolean): void {
  emit('update:enable-intention-classification', value)
}

function handleCollectionsUpdate(value: string[]): void {
  emit('update:selected-collections', value)
}
</script>

<style scoped>
/* Modal animation styles if needed */
</style>
