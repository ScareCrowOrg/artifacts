import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Plugin to mark @/ imports as external (resolved by browser import maps at runtime)
// This allows cell types to import from cockpit-vue without requiring it in the container
const externalCockpitVuePlugin = {
  name: 'external-cockpit-vue',
  enforce: 'pre',
  resolveId(id) {
    // Mark @/ imports as external for browser import map resolution
    if (id.startsWith('@/')) {
      return { id, external: true }
    }
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
    return () => {
      server.middlewares.use((req, res, next) => {
        // Rewrite /artifacts/* URLs to /* for file serving
        if (req.url.startsWith('/artifacts/')) {
          req.url = req.url.replace('/artifacts', '')
        }
        next()
      })
    }
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
    externalCockpitVuePlugin,
    urlRewritePlugin,
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
    cors: {
      origin: [
        'http://localhost:8000',   // nginx proxy
        'http://localhost:5173',   // Vite dev frontend
        'http://localhost:5050',   // ScareRunner
      ],
      credentials: true,
    },

    // HMR (Hot Module Replacement) configuration
    hmr: {
      host: 'localhost',
      port: 5052,
      protocol: 'ws',
    },

    // Serve files from artifacts root
    fs: {
      // Allow serving files from artifacts directory only
      allow: [
        '.',  // artifacts root
      ],
      strict: true,
    },
  },
  
  // Module resolution
  resolve: {
    alias: {
      // Map #artifacts to artifacts root
      '#artifacts': path.resolve(__dirname, '.'),
      // Note: @/ is NOT aliased here - it's marked as external by externalCockpitVuePlugin
      // At runtime, browser import maps resolve @/ to cockpit-vue via http
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
    ],
  },
  
  // Logging
  logLevel: 'info',
  clearScreen: false,  // Don't clear terminal on startup
})
