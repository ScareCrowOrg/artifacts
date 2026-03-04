/**
 * DynamicWorkspace v2 - Phase 1 Entrypoint
 *
 * Simple Vue 3 SPA that bootstraps App.vue (hello world + handshake validation).
 * Renders only after Cockpit ↔ Runner handshake completes.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
