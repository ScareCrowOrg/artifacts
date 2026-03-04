/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Migration Warning Plugin - Pedagogical approach (DISABLED)
// Previously warned about @/ imports, but now @/ is resolved to #shared/ via alias
// This allows shared utilities to use @/ imports which work in both contexts:
// - In cockpit-vue: @/ → cockpit-vue/src (normal resolution)
// - In Vite: @/ → #shared/ (via alias)
const migrationWarningPlugin = {
  name: 'migration-warning',
  enforce: 'pre',
  resolveId(id, importer) {
    // Plugin disabled - @/ is now properly resolved via alias
    // No more warnings needed
  },
}

// Plugin to handle /artifacts/* file serving
const artifactsRewritePlugin = {
  name: 'artifacts-rewrite',
  enforce: 'pre',
  resolveId(id) {
    // Handle /artifacts/ prefixes in import paths
    if (id.startsWith('/artifacts/')) {
      return { id: id.replace('/artifacts', ''), external: false }
    }
  },
  load(id) {
    // Handle /artifacts/ prefixes in file paths from middleware
    if (id.startsWith('/artifacts/')) {
      const newId = id.replace('/artifacts', '')
      return this.load(newId)
    }
  },
}

// Plugin to handle URL rewriting for /artifacts/* requests
// This allows the dev server to serve /artifacts/canonical/... correctly
// when running from /app with root=/app/artifacts
const urlRewritePlugin = {
  name: 'url-rewrite',
  apply: 'serve',
  configureServer(server) {
    // Add middleware to rewrite /artifacts/* URLs to /* for file serving
    server.middlewares.use((req, res, next) => {
      // Rewrite /artifacts/* URLs to /* for file serving
      if (req.url.startsWith('/artifacts/')) {
        req.url = req.url.replace('/artifacts', '')
      }
      next()
    })
  },
}

// Plugin to serve DynamicWorkspace v2 viewer as a standalone SPA.
// Intercepts GET /viewers/:viewerName and returns an HTML page that
// bootstraps the corresponding canonical/viewers/<name>/App.vue.
const viewerPlugin = {
  name: 'viewer-handler',
  apply: 'serve' as const,
  configureServer(server: any) {
    server.middlewares.use((req: any, res: any, next: () => void) => {
      const match = req.url?.match(/^\/viewers\/([^/?#]+)(\/)?(\?.*)?$/)
      if (!match) {
        next()
        return
      }
      const viewerName = match[1]
      const centralhubUrl =
        process.env.VITE_CENTRALHUB_URL || 'http://localhost:5050'

      res.setHeader('Content-Type', 'text/html; charset=utf-8')
      res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DynamicWorkspace v2 – ${viewerName}</title>
  <script type="importmap">
    {
      "imports": {
        "vue": "https://unpkg.com/vue@3/dist/vue.esm-browser.js",
        "pinia": "https://unpkg.com/pinia@latest/dist/pinia.esm-browser.mjs"
      }
    }
  </script>
</head>
<body>
  <div id="app"></div>
  <script type="module">
    import { createApp } from 'vue'
    import { createPinia } from 'pinia'
    import App from '/canonical/viewers/${viewerName}/App.vue'

    const app = createApp(App)
    app.use(createPinia())
    app.mount('#app')
  </script>
</body>
</html>`)
    })
  },
}

/**
 * Vite configuration for ScareVerse Artifacts Compilation Service
 * 
 * This Vite dev server runs as a subprocess within ScareRunner (port 5052)
 * and compiles TypeScript/Vue components on-demand for dynamic cell/book types.
 * 
 * Architecture:
 * - Frontend requests compiled modules via Dynamic Import Maps
 * - Browser resolves #artifacts/ → http://localhost:5052/artifacts/
 * - Vite compiles .ts/.vue files on-demand with source maps
 * - Hot Module Replacement (HMR) enabled for dev convenience
 * 
 * Purpose:
 * - Enable plug-and-play cell types without frontend rebuild
 * - Support BaseCell inheritance natively (no eval())
 * - Provide real debugging with source maps
 * - Allow TypeScript features (generics, decorators, etc)
 */

export default defineConfig({
  root: '/app/artifacts',
  plugins: [
    migrationWarningPlugin,
    urlRewritePlugin,
    viewerPlugin,
    artifactsRewritePlugin,
    vue({
      include: [/\.vue$/],
    })
  ],

  // Development server configuration
  server: {
    port: 5052,
    host: '0.0.0.0',  // Listen on all interfaces (container networking)
    strictPort: true,  // Fail if port 5052 is already in use

    // CORS configuration for cross-origin requests from frontend
    // Can be overridden with VITE_CORS_ORIGINS environment variable
    cors: {
      origin: (process.env.VITE_CORS_ORIGINS || 'http://localhost:8000,http://localhost:5173,http://localhost:5050').split(','),
      credentials: true,
    },

    // HMR (Hot Module Replacement) configuration
    // For local direct access: uses port 5052 directly
    // For proxy scenarios (Nginx on 8000): can override clientPort
    hmr: {
      host: process.env.VITE_HMR_HOST || 'localhost',
      port: parseInt(process.env.VITE_HMR_PORT || '5052'),
      protocol: process.env.VITE_HMR_PROTOCOL || 'ws',
      ...(process.env.VITE_HMR_CLIENT_PORT && {
        clientPort: parseInt(process.env.VITE_HMR_CLIENT_PORT),
      }),
    },

    // Serve files from artifacts root
    fs: {
      // Allow Vite to resolve files from these directories
      // Critical: Use absolute paths for container compatibility
      allow: [
        '/app/artifacts',           // Artifacts root (for all cell types)
        '/app/node_modules',        // Dependencies (Vue, etc)
      ],
      strict: true,
    },
  },
  
  // Module resolution
  resolve: {
    alias: {
      // Use flexible paths for both container and local development
      // In container: /app/artifacts
      // In local/test: process.cwd()
      
      // Map #artifacts to artifacts root (for all cell types and composition)
      '#artifacts': process.cwd(),

      // Map #shared to shared infrastructure mirror (isolated utilities)
      '#shared': path.resolve(process.cwd(), 'shared'),

      // Map @/ to #shared for shared utilities (apiService, authService, etc)
      // This allows files that import @/utils/logger to resolve to #shared/utils/logger
      // In cockpit-vue context: @/ → cockpit-vue/src (normal)
      // In Vite context: @/ → #shared/ (this alias, preserving folder structure)
      '@': path.resolve(process.cwd(), 'shared'),
      '@/utils': path.resolve(process.cwd(), 'shared/utils'),
      '@/services': path.resolve(process.cwd(), 'shared/services'),
      '@/config': path.resolve(process.cwd(), 'shared/config'),
      '@/components': path.resolve(process.cwd(), 'shared/components'),
      '@/types': path.resolve(process.cwd(), 'shared/types'),
      '@/stores': path.resolve(process.cwd(), 'shared/stores'),
      '@/composables': path.resolve(process.cwd(), 'shared/composables'),
      '@/i18n': path.resolve(process.cwd(), 'shared/i18n'),
    },
    extensions: ['.ts', '.tsx', '.vue', '.js', '.jsx', '.json'],
  },
  
  // Build configuration (not used in dev mode, but defined for consistency)
  build: {
    // Not used - this Vite server only runs in dev mode
    target: 'esnext',
    sourcemap: true,
  },
  
  // Optimize dependencies
  optimizeDeps: {
    include: [
      'vue',
      '@vue/runtime-core',
      '@vue/runtime-dom',
      '@babylonjs/core',
      '@babylonjs/loaders',
      '@babylonjs/materials',
    ],
  },
  
  // Logging
  logLevel: 'info',
  clearScreen: false,  // Don't clear terminal on startup
  
  // Test configuration
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    root: process.cwd(),  // Use current working directory for tests
    include: ['**/tests/**/*.{test,spec}.{js,ts,jsx,tsx}', '**/*.{test,spec}.{js,ts,jsx,tsx}'],
    exclude: ['node_modules', 'dist', '.idea', '.git', '.cache'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.test.ts',
        '**/*.test.js',
        '**/*.spec.ts',
        '**/*.spec.js',
        '**/tests/**',
        'vite.config.ts',
        'vitest.config.ts',
        'vitest.setup.ts'
      ],
      all: true,
      lines: 90,
      functions: 90,
      branches: 90,
      statements: 90
    }
  }
})
