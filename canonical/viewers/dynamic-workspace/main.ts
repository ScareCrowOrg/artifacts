/**
 * DynamicWorkspace v2 - Phase 2 Entrypoint - DEBUG MODE
 *
 * Testing imports one by one to find the culprit
 */

// TEST 1: Just Vue
import { createApp } from 'vue'
console.log('[MAIN] Vue imported OK')

// TEST 2: Try Pinia
// import { createPinia } from 'pinia'
// console.log('[MAIN] Pinia imported OK')

// TEST 3: Try App.vue
// import App from './App.vue'
// console.log('[MAIN] App.vue imported OK')

// TEST 4: Try i18n
// import i18n from '@/i18n'
// console.log('[MAIN] i18n imported OK')

// TEST: Minimal app creation
// const app = createApp(App)
// app.use(createPinia())
// app.use(i18n)
// app.mount('#app')

console.log('[MAIN] All tests complete')
