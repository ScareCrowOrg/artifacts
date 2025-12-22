/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-22",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-22",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent"
 * }
 */
<template>
  <div
    v-if="isOpen"
    class="modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 dark:bg-opacity-70"
    @click.self="handleCancel"
  >
    <div
      class="modal-container bg-surface dark:bg-gray-900 rounded-lg shadow-2xl max-w-md w-full mx-4"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
    >
      <!-- Header -->
      <div class="modal-header px-6 py-4 border-b border-border dark:border-gray-700">
        <h2 :id="titleId" class="text-xl font-bold text-text-primary dark:text-text-primary flex items-center gap-2">
          <span>🔐</span>
          <span>{{ $t('vault.unlockModal.title') }}</span>
        </h2>
      </div>

      <!-- Body -->
      <form @submit.prevent="handleUnlock">
        <div class="modal-body p-6 space-y-4">
          <p class="text-sm text-text-secondary dark:text-text-secondary">
            {{ $t('vault.unlockModal.description') }}
          </p>

          <!-- Password Input -->
          <div>
            <label
              :for="passwordInputId"
              class="block text-sm font-medium text-text-primary dark:text-text-primary mb-2"
            >
              {{ $t('vault.unlockModal.masterPassword') }}
            </label>
            <input
              :id="passwordInputId"
              ref="passwordInput"
              v-model="password"
              type="password"
              class="w-full px-4 py-2 border border-border dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary bg-surface dark:bg-gray-800 text-text-primary dark:text-text-primary"
              :placeholder="$t('vault.unlockModal.passwordPlaceholder')"
              :aria-label="$t('vault.unlockModal.masterPassword')"
              required
              autocomplete="off"
            />
          </div>

          <!-- Error Message -->
          <div v-if="error" class="error-message p-3 bg-error bg-opacity-10 border border-error rounded-lg">
            <p class="text-sm text-error dark:text-error flex items-center gap-2">
              <span>⚠️</span>
              <span>{{ error }}</span>
            </p>
          </div>

          <!-- Security Notice -->
          <div class="security-notice p-3 bg-primary bg-opacity-10 border border-primary dark:border-primary-light rounded-lg">
            <p class="text-xs text-text-secondary dark:text-text-secondary">
              {{ $t('vault.unlockModal.securityNotice') }}
            </p>
          </div>
        </div>

        <!-- Footer -->
        <div class="modal-footer px-6 py-4 border-t border-border dark:border-gray-700 flex items-center justify-end gap-3">
          <button
            type="button"
            class="btn btn-secondary"
            @click="handleCancel"
          >
            {{ $t('vault.unlockModal.cancel') }}
          </button>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="!password || isUnlocking"
          >
            <span v-if="isUnlocking">{{ $t('vault.unlockModal.unlocking') }}</span>
            <span v-else>{{ $t('vault.unlockModal.unlock') }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

// Generate unique IDs for accessibility
const titleId = `vault-unlock-title-${Math.random().toString(36).substr(2, 9)}`
const passwordInputId = `vault-password-${Math.random().toString(36).substr(2, 9)}`

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['unlock', 'cancel'])

// Local state
const password = ref('')
const error = ref(null)
const isUnlocking = ref(false)
const passwordInput = ref(null)

// Watch for modal open to focus input
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen) {
    // Reset state
    password.value = ''
    error.value = null
    isUnlocking.value = false
    
    // Focus password input
    await nextTick()
    passwordInput.value?.focus()
  }
})

/**
 * Handle unlock attempt
 */
async function handleUnlock() {
  if (!password.value) {
    error.value = $t('vault.unlockModal.errors.passwordRequired')
    return
  }

  isUnlocking.value = true
  error.value = null

  try {
    // Emit unlock event with password
    emit('unlock', password.value)
  } catch (err) {
    error.value = err.message || $t('vault.unlockModal.errors.unlockFailed')
    isUnlocking.value = false
  }
}

/**
 * Handle cancel
 */
function handleCancel() {
  password.value = ''
  error.value = null
  emit('cancel')
}

/**
 * Set error from parent
 */
function setError(message) {
  error.value = message
  isUnlocking.value = false
}

// Expose methods to parent
defineExpose({
  setError
})
</script>

<style scoped>
/* Modal animations */
.modal-overlay {
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-container {
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
