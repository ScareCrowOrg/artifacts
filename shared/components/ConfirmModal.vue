<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="confirm-modal-overlay"
      @click.self="handleCancel"
    >
      <div class="confirm-modal bg-surface dark:bg-surface-dark border border-border dark:border-border-dark rounded-lg shadow-xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 border-b border-border dark:border-border-dark">
          <h3 class="text-sm font-semibold text-text-primary dark:text-text-primary-dark">
            {{ title }}
          </h3>
          <button
            @click="handleCancel"
            class="text-text-secondary dark:text-text-secondary-dark hover:text-text-primary dark:hover:text-text-primary-dark transition"
            :disabled="loading"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Message -->
        <div class="px-4 py-4">
          <p class="text-sm text-text-primary dark:text-text-primary-dark whitespace-pre-wrap">
            {{ message }}
          </p>
        </div>

        <!-- Error -->
        <div
          v-if="error"
          class="mx-4 mb-2 px-3 py-2 text-xs text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 rounded"
        >
          {{ error }}
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 px-4 py-3 border-t border-border dark:border-border-dark">
          <button
            @click="handleCancel"
            class="px-3 py-1.5 text-xs font-medium text-text-primary dark:text-text-primary-dark bg-surface-alt dark:bg-surface-alt-dark rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition"
            :disabled="loading"
          >
            {{ cancelText }}
          </button>
          <button
            @click="handleConfirm"
            class="px-3 py-1.5 text-xs font-medium text-white rounded transition disabled:opacity-50 disabled:cursor-not-allowed"
            :class="danger
              ? 'bg-red-600 hover:bg-red-700'
              : 'bg-primary hover:bg-primary-hover'"
            :disabled="loading"
          >
            <span v-if="loading" class="inline-flex items-center gap-1">
              <svg class="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {{ confirmText }}
            </span>
            <span v-else>{{ confirmText }}</span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * ConfirmModal — reusable confirmation dialog component.
 *
 * Usage:
 *   <ConfirmModal
 *     :visible="showModal"
 *     title="Confirm Action"
 *     message="Are you sure?"
 *     @confirm="onConfirm"
 *     @cancel="showModal = false"
 *   />
 */
defineProps<{
  visible: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  loading?: boolean
  error?: string
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  emit('cancel')
}
</script>

<style scoped>
.confirm-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}

.confirm-modal {
  width: 90%;
  max-width: 400px;
}
</style>
