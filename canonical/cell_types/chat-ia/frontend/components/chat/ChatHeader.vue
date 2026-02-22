/**
 * @metadata {
 *   "theme_validated": true,
 *   "theme_validated_date": "2025-12-11",
 *   "theme_compliance": 100,
 *   "theme_status": "excellent",
 *   "theme_issues": 0,
 *   "dark_mode_support": "full",
 *   "i18n_validated": true,
 *   "i18n_validated_date": "2025-12-12",
 *   "i18n_coverage": 100,
 *   "i18n_status": "excellent",
 *   "i18n_issues_found": 0,
 *   "logging_validated": true,
 *   "logging_validated_date": "2025-01-26",
 *   "console_calls_found": 42,
 *   "console_calls_migrated": 42,
 *   "logger_namespace": "chat:header",
 *   "migration_status": "complete"
 * }
 */
<template>
  <div
    class="flex justify-between items-center border-b p-4"
    style="background: var(--color-surface); border-color: var(--color-border);"
  >
    <div class="flex items-center gap-4">
      <h3 class="text-lg font-semibold" style="color: var(--color-text-primary);">
        {{ $t('chatHeader.title') }}
      </h3>
      
      <!-- Agent Mode Toggle (MVP 4) -->
      <div class="flex items-center gap-2">
        <label
          class="text-sm font-medium"
          style="color: var(--color-text-secondary);"
          :title="$t('chatHeader.agentModeTooltip')"
        >
          {{ $t('chatHeader.agentModeLabel') }}
        </label>
        <button
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2"
          :class="chatStore.isAgentMode ? 'bg-primary-500' : 'bg-gray-300 dark:bg-gray-600'"
          :style="chatStore.isAgentMode ? 'box-shadow: 0 0 8px rgba(59, 130, 246, 0.5);' : ''"
          role="switch"
          :aria-checked="chatStore.isAgentMode"
          :aria-label="$t('chatHeader.agentModeToggle')"
          data-testid="agent-mode-toggle"
          @click="handleAgentModeToggle"
        >
          <span
            class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200"
            :class="chatStore.isAgentMode ? 'translate-x-6' : 'translate-x-1'"
          />
        </button>
        
        <!-- Live-Wire Badge (when Agent Mode active) -->
        <transition name="fade">
          <span
            v-if="chatStore.isAgentMode"
            class="px-2 py-1 text-xs font-semibold rounded-full border animate-pulse"
            style="
              background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(147, 51, 234, 0.1));
              color: var(--color-primary);
              border-color: var(--color-primary);
            "
            data-testid="live-wire-badge"
          >
            ⚡ {{ $t('chatHeader.liveWire') }}
          </span>
        </transition>
      </div>
    </div>
    
    <div class="flex gap-2">
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors duration-200 border"
        style="background: var(--color-surface); color: var(--color-text-secondary); border-color: var(--color-border);"
        :title="
          uiStore.showChatSettings
            ? $t('chatHeader.hideSettings')
            : $t('chatHeader.showSettings')
        "
        :aria-label="
          uiStore.showChatSettings
            ? $t('chatHeader.hideSettingsLabel')
            : $t('chatHeader.showSettingsLabel')
        "
        :aria-expanded="uiStore.showChatSettings"
        data-testid="toggle-settings-button"
        @click="handleSettingsToggle"
        @mouseenter="$event.target.style.background = 'var(--color-surface-hover)'"
        @mouseleave="$event.target.style.background = 'var(--color-surface)'"
      >
        {{ $t('chatHeader.settingsButton') }}
      </button>
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors duration-200 border"
        style="background: var(--color-surface); color: var(--color-text-secondary); border-color: var(--color-border);"
        :title="$t('chatHeader.historyTooltip')"
        :aria-label="$t('chatHeader.historyLabel')"
        data-testid="toggle-history-button"
        @click="uiStore.toggleChatHistory"
        @mouseenter="$event.target.style.background = 'var(--color-surface-hover)'"
        @mouseleave="$event.target.style.background = 'var(--color-surface)'"
      >
        {{ $t('chatHeader.historyButton') }}
      </button>
      <button
        class="px-3 py-1.5 text-sm rounded-md transition-colors duration-200 border"
        style="background: var(--color-surface); color: var(--color-text-secondary); border-color: var(--color-border);"
        :title="$t('chatHeader.clearTooltip')"
        :aria-label="$t('chatHeader.clearLabel')"
        data-testid="clear-chat-button"
        @click="uiStore.clearChat"
        @mouseenter="$event.target.style.background = 'var(--color-surface-hover)'"
        @mouseleave="$event.target.style.background = 'var(--color-surface)'"
      >
        {{ $t('chatHeader.clearButton') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { useChatStore } from '../../stores/chat'
import { useUIStore } from '../../stores/ui'
import { onMounted } from 'vue'
import { createLogger } from '@/utils/logger'

const log = createLogger('chat:header')
const chatStore = useChatStore()
const uiStore = useUIStore()

// DEBUG LOG #3: Inspeção do objeto store (chat)
log.debug('[DEBUG][ITERATION_1] ChatHeader.vue - Chat Store instance created')
log.debug('[DEBUG][ITERATION_1] Chat Store keys:', Object.keys(chatStore))
log.debug('[DEBUG][ITERATION_1] Has isAgentMode:', 'isAgentMode' in chatStore)
log.debug('[DEBUG][ITERATION_1] Has toggleAgentMode:', 'toggleAgentMode' in chatStore)
log.debug('[DEBUG][ITERATION_1] isAgentMode value:', chatStore.isAgentMode)
log.debug('[DEBUG][ITERATION_1] toggleAgentMode type:', typeof chatStore.toggleAgentMode)

// DEBUG LOG (ITERATION #2): Inspeção do objeto UI store
log.debug('[DEBUG][ITERATION_2] ChatHeader.vue - UI Store instance created')
log.debug('[DEBUG][ITERATION_2] UI Store keys:', Object.keys(uiStore))
log.debug('[DEBUG][ITERATION_2] Has showChatSettings:', 'showChatSettings' in uiStore)
log.debug('[DEBUG][ITERATION_2] Has toggleChatSettings:', 'toggleChatSettings' in uiStore)
log.debug('[DEBUG][ITERATION_2] showChatSettings value:', uiStore.showChatSettings)
log.debug('[DEBUG][ITERATION_2] toggleChatSettings type:', typeof uiStore.toggleChatSettings)
log.debug('[DEBUG][ITERATION_2] Full UI store object:', uiStore)

// DEBUG LOG #4: Button click handler wrapper (Agent Mode)
function handleAgentModeToggle() {
  log.debug('[DEBUG][ITERATION_1] Agent Mode toggle button CLICKED')
  log.debug('[DEBUG][ITERATION_1] Current isAgentMode value:', chatStore.isAgentMode)
  log.debug('[DEBUG][ITERATION_1] toggleAgentMode exists?', !!chatStore.toggleAgentMode)
  log.debug('[DEBUG][ITERATION_1] toggleAgentMode type:', typeof chatStore.toggleAgentMode)
  
  if (typeof chatStore.toggleAgentMode === 'function') {
    log.debug('[DEBUG][ITERATION_1] Calling toggleAgentMode()...')
    try {
      chatStore.toggleAgentMode()
      log.debug('[DEBUG][ITERATION_1] toggleAgentMode() called successfully')
      log.debug('[DEBUG][ITERATION_1] New isAgentMode value:', chatStore.isAgentMode)
    } catch (error) {
      log.error('[DEBUG][ITERATION_1] ERROR calling toggleAgentMode:', error)
      log.error('[DEBUG][ITERATION_1] Error stack:', error.stack)
    }
  } else {
    log.error('[DEBUG][ITERATION_1] ❌ CRITICAL: toggleAgentMode is not a function!')
    log.error('[DEBUG][ITERATION_1] ❌ This confirms chat.js is being used instead of chat.ts')
    log.error('[DEBUG][ITERATION_1] Available store methods:', Object.keys(chatStore).filter(k => typeof chatStore[k] === 'function'))
  }
}

// DEBUG LOG (ITERATION #2): Settings button click handler wrapper
function handleSettingsToggle() {
  log.debug('[DEBUG][ITERATION_2] Settings toggle button CLICKED')
  log.debug('[DEBUG][ITERATION_2] Current showChatSettings value:', uiStore.showChatSettings)
  log.debug('[DEBUG][ITERATION_2] toggleChatSettings exists?', !!uiStore.toggleChatSettings)
  log.debug('[DEBUG][ITERATION_2] toggleChatSettings type:', typeof uiStore.toggleChatSettings)
  
  if (typeof uiStore.toggleChatSettings === 'function') {
    log.debug('[DEBUG][ITERATION_2] Calling toggleChatSettings()...')
    try {
      uiStore.toggleChatSettings()
      log.debug('[DEBUG][ITERATION_2] toggleChatSettings() called successfully')
      log.debug('[DEBUG][ITERATION_2] New showChatSettings value:', uiStore.showChatSettings)
    } catch (error) {
      log.error('[DEBUG][ITERATION_2] ERROR calling toggleChatSettings:', error)
      log.error('[DEBUG][ITERATION_2] Error stack:', error.stack)
    }
  } else {
    log.error('[DEBUG][ITERATION_2] ❌ CRITICAL: toggleChatSettings is not a function!')
    log.error('[DEBUG][ITERATION_2] ❌ This confirms ui.js is being used instead of ui.ts')
    log.error('[DEBUG][ITERATION_2] Available UI store methods:', Object.keys(uiStore).filter(k => typeof uiStore[k] === 'function'))
  }
}

// DEBUG LOG #5: Vue component mount detection
onMounted(() => {
  log.debug('[DEBUG][ITERATION_1] ChatHeader.vue mounted')
  log.debug('[DEBUG][ITERATION_1] Initial Agent Mode state:', chatStore.isAgentMode)
  log.debug('[DEBUG][ITERATION_1] Agent Mode button element:', document.querySelector('[data-testid="agent-mode-toggle"]'))
  
  log.debug('[DEBUG][ITERATION_2] Initial Settings state:', uiStore.showChatSettings)
  log.debug('[DEBUG][ITERATION_2] Settings button element:', document.querySelector('[data-testid="toggle-settings-button"]'))
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
