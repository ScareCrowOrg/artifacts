/**
 * @metadata {
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-12",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full"
 * }
 */
<template>
  <div class="loading-indicator">
    <div class="loading-header">
      <span class="ai-icon">🤖</span>
      <span class="ai-label">{{ $t('chat.loadingIndicator.aiLabel') }}</span>
    </div>
    <div class="typing-indicator">
      <span class="typing-dot"></span>
      <span class="typing-dot typing-dot-delay-1"></span>
      <span class="typing-dot typing-dot-delay-2"></span>
    </div>
  </div>
</template>

<script setup>
// Simple presentational component with no logic
</script>

<style scoped>
.loading-indicator {
  margin-bottom: var(--space-md);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  margin-right: var(--space-xl);
}

.loading-header {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.ai-icon {
  font-size: var(--font-size-lg);
}

.ai-label {
  font-weight: var(--font-weight-semibold);
}

.typing-indicator {
  display: flex;
  gap: var(--space-xs);
}

.typing-dot {
  width: 8px;
  height: 8px;
  background: var(--color-text-tertiary);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-dot-delay-1 {
  animation-delay: 0.2s;
}

.typing-dot-delay-2 {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%,
  60%,
  100% {
    opacity: 0.3;
  }
  30% {
    opacity: 1;
  }
}
</style>
