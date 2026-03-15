/**
 * DynamicWorkspace v2 - Phase 2 Entrypoint
 *
 * Vue 3 SPA with:
 * - Pinia for workspace state (handshake store)
 * - vue-i18n for translations (layout.* keys from v1)
 * - App.vue orchestrates grid, BaseCell instantiation, and view resolution
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import i18n from './i18n'

const app = createApp(App)
app.use(createPinia())
app.use(i18n)

// ⚡ CRITICAL: Make i18n available globally for dynamically loaded components
// This ensures isolated components (like cells) can access i18n even if useI18n() fails
if (typeof window !== 'undefined') {
  window['__i18n'] = i18n
  console.log('[DynamicWorkspace] i18n registered in window for isolated component access')
}

app.mount('#app')
