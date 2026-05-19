import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import en from './i18n/en.json'
import pt from './i18n/pt.json'

const i18n = createI18n({
  legacy: false,
  locale: navigator.language?.split('-')[0] || 'en',
  fallbackLocale: 'en',
  messages: { en, pt },
})

const app = createApp(App)
app.use(i18n)
app.mount('#app')
