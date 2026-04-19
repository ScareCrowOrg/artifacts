import { createApp } from 'vue'
import App from './App.vue'

let sessionToken: string | null = null
let appReady = false

// Set up listener BEFORE mounting app - ensures we catch INIT_WORKSPACE immediately
window.addEventListener('message', (event) => {
  const message = event.data

  if (message?.type === 'INIT_WORKSPACE') {
    console.log('[HMR-Test] Received INIT_WORKSPACE from ViewerShell')
    sessionToken = message.payload?.sessionToken

    if (!appReady && sessionToken) {
      console.log('[HMR-Test] Session token received, mounting app')
      mountApp()
    }
  }
})

function mountApp() {
  const app = createApp(App)
  app.provide('sessionToken', sessionToken)
  app.mount('#app')
  appReady = true
}

// Timeout fallback: mount app after 2s even if no INIT_WORKSPACE received
setTimeout(() => {
  if (!appReady) {
    console.warn('[HMR-Test] No INIT_WORKSPACE received, mounting app anyway')
    mountApp()
  }
}, 2000)
