# Adding a New Viewer

> **Audience**: Users of the ScareVerse platform implementing custom viewers with AI assistance.

---

## Overview

A **Viewer** is a standalone Vue 3 application that runs as a micro-frontend within the ScareVerse ecosystem. Viewers are independently routed, served by Vite, and authenticated via the Auth-Proxy gateway.

### When to Create a Viewer

- You need a **dedicated page/interface** outside the notebook/cell model
- The interface is **independent** (doesn't need iframe parent communication)
- Examples: inbox, dashboard, admin panel, public landing page

### When NOT to Create a Viewer

- Use a **Cell** when you need a reusable component inside a notebook
- Use a **Book** when orchestrating multiple cells in a workflow

---

## Pré-requisites

### Directory Structure

```
artifacts/canonical/viewers/my-viewer/
├── index.html        # Entry HTML (loads main.ts)
├── main.ts           # Vue app bootstrap
├── App.vue           # Root component with useBaseViewer
├── en.json           # English i18n messages
└── pt.json           # Portuguese i18n messages
```

### The `useBaseViewer` Composable

`useBaseViewer` provides everything a standalone viewer needs:

| Concern | Provided by `useBaseViewer` | You Implement |
|---------|----------------------------|---------------|
| API URL resolution | `API_BASE`, `normalizePath()` | — |
| HTTP client | `apiFetch()` (cookie-based, no Pinia) | — |
| Auth detection | `checkAuth()`, `bindSession()`, `isAuthenticated` | — |
| Loading/error states | `loadingState`, `errorMessage`, `loadData()` | — |
| Date formatting | `formatDate()` | — |
| Viewer-specific logic | — | Forms, lists, grids, themes |

---

## Step-by-Step

### 1. Create the viewer directory

```bash
mkdir -p artifacts/canonical/viewers/my-viewer
```

### 2. Create `index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>My Viewer</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="./main.ts"></script>
</body>
</html>
```

### 3. Create `main.ts`

```typescript
import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import en from './en.json'
import pt from './pt.json'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, pt },
})

const app = createApp(App)
app.use(i18n)
app.mount('#app')
```

### 4. Create `App.vue` with `useBaseViewer`

```vue
<template>
  <div class="my-viewer">
    <header>
      <h1>{{ $t('myViewer.title') }}</h1>
      <div v-if="!isAuthenticated">
        <a href="/">{{ $t('myViewer.login') }}</a>
      </div>
    </header>

    <main>
      <!-- Loading indicator -->
      <div v-if="loadingState">
        <p>{{ $t('myViewer.loading') }}</p>
      </div>

      <!-- Error banner -->
      <div v-if="errorMessage" role="alert">
        {{ errorMessage }}
      </div>

      <template v-if="!loadingState">
        <!-- Not authenticated notice -->
        <div v-if="!isAuthenticated">
          <p>{{ $t('myViewer.notAuthenticated') }}</p>
          <a href="/">{{ $t('myViewer.loginButton') }}</a>
        </div>

        <!-- Authenticated content -->
        <div v-if="isAuthenticated">
          <p>Welcome! Your viewer logic goes here.</p>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useBaseViewer } from '@/composables/useBaseViewer'

const {
  loadingState, errorMessage, isAuthenticated,
  apiFetch, checkAuth, formatDate, loadData,
} = useBaseViewer()

// Viewer-specific state
const items = ref<any[]>([])

async function loadItems() {
  await checkAuth()
  if (isAuthenticated.value) {
    const data = await apiFetch('/api/my-endpoint')
    items.value = Array.isArray(data) ? data : []
  }
}

onMounted(() => {
  loadData(loadItems)
})
</script>
```

### 5. Create i18n files

**`en.json`**:
```json
{
  "myViewer": {
    "title": "My Viewer",
    "loading": "Loading...",
    "notAuthenticated": "You are not logged in.",
    "login": "Login",
    "loginButton": "Go to Login"
  }
}
```

**`pt.json`**:
```json
{
  "myViewer": {
    "title": "Meu Visualizador",
    "loading": "Carregando...",
    "notAuthenticated": "Você não está logado.",
    "login": "Entrar",
    "loginButton": "Ir para Login"
  }
}
```

### 6. (Optional) Register the viewer path

If your viewer needs to be accessible via Auth-Proxy, add its root path to `PUBLIC_PREFIXES` in the auth-proxy configuration:

```
artifacts/canonical/viewers/my-viewer/
```

The viewer is automatically served by Vite at `/artifacts/canonical/viewers/my-viewer/`.

---

## API Reference: `useBaseViewer`

```typescript
import { useBaseViewer } from '@/composables/useBaseViewer'
const { ... } = useBaseViewer()
```

| Return | Type | Description |
|--------|------|-------------|
| `API_BASE` | `string` | Resolved API base URL (from `window.API_BASE_URL` or `VITE_API_BASE_URL`) |
| `normalizePath(path)` | `(path: string) => string` | Normalizes a path to a full URL: `/inbox` → `{API_BASE}/api/inbox`, `/api/inbox` → `{API_BASE}/api/inbox` |
| `loadingState` | `Ref<boolean>` | Reactive — `true` while `loadData()` is executing |
| `errorMessage` | `Ref<string>` | Reactive — set when `apiFetch()` or `loadData()` catches an error |
| `isAuthenticated` | `Ref<boolean>` | Reactive — set by `checkAuth()` |
| `sessionToken` | `Ref<string>` | Reactive — JWT token read from localStorage (if found) |
| `apiFetch(path, options?)` | `(path: string, options?: RequestInit) => Promise<any>` | Delegates to `apiService.apiFetch` (unified fetch). In standalone viewers (no Pinia), uses `credentials: 'include'` cookie auth. Parses JSON. Sets `errorMessage` on failure. |
| `bindSession(token)` | `(token: string) => Promise<boolean>` | Exchange JWT for httpOnly session cookie via `POST /api/v1/auth/session-bind` |
| `checkAuth()` | `() => Promise<void>` | Two-step auth detection: (1) localStorage JWT → session-bind → httpOnly cookie; (2) fallback cookie probe |
| `loadData(loader)` | `(loader: () => Promise<void>) => Promise<void>` | Lifecycle helper: sets `loadingState = true`, clears `errorMessage`, calls `loader()`, sets `loadingState = false` |
| `formatDate(isoStr?)` | `(isoStr?: string) => string` | Formats ISO date string to locale date (e.g., "May 19, 2026") |

### What `useBaseViewer` Does NOT Provide

| Concern | Why Not |
|---------|---------|
| postMessage handshake | Only needed by Dynamic Workspace (iframe parent communication) |
| Pinia stores / workspaceStore | Viewers are standalone — no store dependency |
| UI components / CSS | Viewer-specific decision |
| Form validation | Viewer-specific logic |
| Grid layout / cells | Cell/Book architecture, not viewer |

---

## Complete Example: Public Inbox Viewer

See `artifacts/canonical/viewers/planet-hall/` for a complete, production-quality implementation using `useBaseViewer`. It demonstrates:

- Public content (messages) visible without auth
- Authenticated content (requests, create forms) guarded by `v-if="isAuthenticated"`
- Loading state and error banner patterns
- Form submission with `apiFetch`
- i18n with `$t()`

---

## Validation

1. **Start Vite**: The viewer should compile without errors when accessed at `/artifacts/canonical/viewers/my-viewer/`
2. **Check auth flow**: Login → JWT stored in localStorage → `checkAuth()` binds session → `isAuthenticated` becomes `true`
3. **Check API calls**: `apiFetch()` sends `credentials: 'include'` — the Auth-Proxy forwards the session cookie to Backend

---

> **Last Updated**: 2026-05-19
> **Version**: 1.0.0
