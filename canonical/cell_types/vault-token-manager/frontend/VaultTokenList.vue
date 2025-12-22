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
  <div class="vault-token-list">
    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center py-8">
      <div class="text-center">
        <div class="spinner mb-3"></div>
        <p class="text-sm text-text-secondary dark:text-text-secondary">
          {{ $t('vault.tokenList.loading') }}
        </p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-container p-4 bg-error bg-opacity-10 border border-error rounded-lg">
      <p class="text-sm text-error dark:text-error flex items-center gap-2">
        <span>⚠️</span>
        <span>{{ error }}</span>
      </p>
      <button class="btn btn-sm btn-secondary mt-3" @click="$emit('refresh')">
        {{ $t('vault.tokenList.retry') }}
      </button>
    </div>

    <!-- Empty State -->
    <div v-else-if="sortedTokens.length === 0" class="empty-state text-center py-12">
      <div class="text-6xl mb-4">🔐</div>
      <h3 class="text-lg font-semibold text-text-primary dark:text-text-primary mb-2">
        {{ $t('vault.tokenList.empty.title') }}
      </h3>
      <p class="text-sm text-text-secondary dark:text-text-secondary mb-4">
        {{ $t('vault.tokenList.empty.description') }}
      </p>
      <button class="btn btn-primary" @click="$emit('add-token')">
        {{ $t('vault.tokenList.empty.addFirst') }}
      </button>
    </div>

    <!-- Token Cards -->
    <div v-else class="token-grid space-y-3">
      <div
        v-for="token in sortedTokens"
        :key="token.vaultRef"
        class="token-card bg-surface-hover dark:bg-gray-800 border border-border dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-all"
        :class="{ 'opacity-50': isTokenExpired(token) }"
      >
        <div class="flex items-start justify-between">
          <!-- Token Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <span class="text-2xl">{{ getProviderIcon(token.provider) }}</span>
              <h4 class="font-semibold text-text-primary dark:text-text-primary truncate">
                {{ token.vaultRef }}
              </h4>
              <span
                v-if="isTokenExpired(token)"
                class="px-2 py-0.5 text-xs bg-error bg-opacity-20 text-error dark:text-error rounded"
              >
                {{ $t('vault.tokenList.expired') }}
              </span>
            </div>

            <div class="space-y-1 text-sm text-text-secondary dark:text-text-secondary">
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ $t('vault.tokenList.provider') }}:</span>
                <span>{{ token.provider }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ $t('vault.tokenList.type') }}:</span>
                <span>{{ token.credentialType || 'api_key' }}</span>
              </div>
              <div v-if="token.createdAt" class="flex items-center gap-2">
                <span class="font-medium">{{ $t('vault.tokenList.created') }}:</span>
                <span>{{ formatDate(token.createdAt) }}</span>
              </div>
              <div v-if="token.expiresAt" class="flex items-center gap-2">
                <span class="font-medium">{{ $t('vault.tokenList.expires') }}:</span>
                <span :class="{ 'text-error dark:text-error': isTokenExpired(token) }">
                  {{ formatDate(token.expiresAt) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2 ml-4">
            <button
              class="btn-icon hover:bg-primary hover:text-white transition-colors"
              :title="$t('vault.tokenList.actions.view')"
              :aria-label="$t('vault.tokenList.actions.viewToken', { ref: token.vaultRef })"
              @click="$emit('view-token', token)"
            >
              <span>👁️</span>
            </button>
            <button
              class="btn-icon hover:bg-error hover:text-white transition-colors"
              :title="$t('vault.tokenList.actions.delete')"
              :aria-label="$t('vault.tokenList.actions.deleteToken', { ref: token.vaultRef })"
              @click="$emit('delete-token', token)"
            >
              <span>🗑️</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t: $t } = useI18n()

const props = defineProps({
  tokens: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  error: {
    type: String,
    default: null
  },
  showExpired: {
    type: Boolean,
    default: false
  },
  sortBy: {
    type: String,
    default: 'createdAt'
  },
  sortOrder: {
    type: String,
    default: 'desc'
  }
})

defineEmits(['refresh', 'add-token', 'view-token', 'delete-token'])

/**
 * Check if token is expired
 */
function isTokenExpired(token) {
  if (!token.expiresAt) return false
  return new Date(token.expiresAt) < new Date()
}

/**
 * Filter and sort tokens
 */
const sortedTokens = computed(() => {
  let filtered = props.tokens

  // Filter expired tokens if needed
  if (!props.showExpired) {
    filtered = filtered.filter(token => !isTokenExpired(token))
  }

  // Sort tokens
  const sorted = [...filtered].sort((a, b) => {
    let comparison = 0
    
    switch (props.sortBy) {
      case 'provider':
        comparison = a.provider.localeCompare(b.provider)
        break
      case 'vaultRef':
        comparison = a.vaultRef.localeCompare(b.vaultRef)
        break
      case 'createdAt':
      default:
        const aDate = new Date(a.createdAt || 0)
        const bDate = new Date(b.createdAt || 0)
        comparison = aDate - bDate
        break
    }

    return props.sortOrder === 'asc' ? comparison : -comparison
  })

  return sorted
})

/**
 * Get provider icon
 */
function getProviderIcon(provider) {
  const icons = {
    openai: '🤖',
    anthropic: '🧠',
    google: '🔍',
    github: '🐙',
    gitlab: '🦊',
    aws: '☁️',
    azure: '💠',
    default: '🔑'
  }
  return icons[provider.toLowerCase()] || icons.default
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}
</script>

<style scoped>
/* Loading spinner */
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-left-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
