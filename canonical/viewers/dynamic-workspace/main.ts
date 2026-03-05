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
app.mount('#app')
