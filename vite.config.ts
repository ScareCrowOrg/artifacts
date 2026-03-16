/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

// Performance Tracing Plugin - Detailed startup timing
const performanceTracingPlugin = {
  name: 'performance-tracing',
  apply: 'serve',
  enforce: 'pre',

  resolveId(id) {
    const shouldTrace = process.env.VITE_TRACE === 'true' || process.env.VITE_TRACE_RESOLVE === 'true';
    if (shouldTrace) {
      const start = performance.now();
      return () => {
        const duration = (performance.now() - start).toFixed(2);
        if (duration > 50) {
          console.error(`  ⏱️ [RESOLVE] ${duration.padStart(6)}ms | ${id}`);
        }
      };
    }
  },

  load(id) {
    const shouldTrace = process.env.VITE_TRACE === 'true' || process.env.VITE_TRACE_LOAD === 'true';
    if (shouldTrace) {
      const start = performance.now();
      return () => {
        const duration = (performance.now() - start).toFixed(2);
        if (duration > 100) {
          console.error(`  ⏱️ [LOAD] ${duration.padStart(6)}ms | ${id}`);
        }
      };
    }
  },

  configureServer(server) {
    const initStart = performance.now();
    const shouldTrace = process.env.VITE_TRACE === 'true';

    console.error('\n' + '━'.repeat(100));
    console.error('🚀 VITE INITIALIZATION STARTED');
    console.error(`   Trace enabled: ${shouldTrace}`);
    console.error(`   Node env: ${process.env.NODE_ENV}`);
    console.error(`   Root: ${process.cwd()}`);
    console.error('━'.repeat(100));

    // Log environment variables for debugging
    console.error('\n📋 ENVIRONMENT VARIABLES:');
    console.error(`   VITE_TRACE: ${process.env.VITE_TRACE ?? 'undefined'}`);
    console.error(`   VITE_TRACE_RESOLVE: ${process.env.VITE_TRACE_RESOLVE ?? 'undefined'}`);
    console.error(`   VITE_TRACE_LOAD: ${process.env.VITE_TRACE_LOAD ?? 'undefined'}`);
    console.error(`   VITE_DEBUG: ${process.env.VITE_DEBUG ?? 'undefined'}`);
    console.error(`   VITE_CORS_ORIGINS: ${process.env.VITE_CORS_ORIGINS ?? 'undefined'}`);
    console.error(`   VITE_COCKPIT_ORIGINS: ${process.env.VITE_COCKPIT_ORIGINS ?? 'undefined'}`);
    console.error(`   VITE_CENTRALHUB_URL: ${process.env.VITE_CENTRALHUB_URL ?? 'undefined'}`);
    console.error(`   VITE_HMR_HOST: ${process.env.VITE_HMR_HOST ?? 'undefined'}`);
    console.error(`   VITE_HMR_PORT: ${process.env.VITE_HMR_PORT ?? 'undefined'}`);
    console.error(`   VITE_HMR_PROTOCOL: ${process.env.VITE_HMR_PROTOCOL ?? 'undefined'}`);
    console.error('━'.repeat(100) + '\n');

    // Track first request and server ready
    let firstRequest = true;
    let serverReady = false;

    // Hook into Vite's ready event
    server.httpServer?.once('listening', () => {
      const readyDuration = (performance.now() - initStart).toFixed(2);
      serverReady = true;
      console.error('\n' + '─'.repeat(100));
      console.error(`✅ VITE SERVER READY`);
      console.error(`   Duration: ${readyDuration}ms`);
      console.error(`   Listening on: http://0.0.0.0:${server.config.server.port}`);
      console.error('─'.repeat(100) + '\n');
    });

    server.middlewares.use((req, res, next) => {
      if (firstRequest && !req.url.includes('__vite') && !req.url.includes('node_modules')) {
        firstRequest = false;
        const totalDuration = (performance.now() - initStart).toFixed(2);
        console.error('\n' + '─'.repeat(100));
        console.error(`📍 FIRST REQUEST RECEIVED`);
        console.error(`   Path: ${req.url}`);
        console.error(`   Total startup time: ${totalDuration}ms`);
        console.error(`   Server ready: ${serverReady}`);
        console.error('─'.repeat(100) + '\n');
      }
      next();
    });
  },
}

// Rebuild Observability Plugin - Logs file change triggers
const rebuildObservabilityPlugin = {
  name: 'rebuild-observability',
  apply: 'serve',
  handleHotUpdate({ file, server, modules }) {
    const timestamp = new Date().toISOString();
    const relativePath = file.replace(process.cwd() + '/', '');
    console.error(`\n🔄 [${timestamp}] HMR Update Triggered`);
    console.error(`   File: ${relativePath}`);
    console.error(`   Affected modules: ${modules.length}`);
    if (modules.length > 0) {
      modules.forEach((mod, idx) => {
        console.error(`     ${idx + 1}. ${mod.url || mod.id}`);
      });
    }
  },
  configureServer(server) {
    console.error('\n⚙️ [Rebuild Plugin] configureServer called - watcher initialized');

    // Monitor file watch events
    const originalWatcher = server.watcher;
    if (originalWatcher) {
      console.error('✅ [Rebuild Plugin] Watcher found, attaching listeners');

      originalWatcher.on('change', (file) => {
        const timestamp = new Date().toISOString();
        const relativePath = file.replace(process.cwd() + '/', '');
        console.error(`📝 [${timestamp}] File changed: ${relativePath}`);
      });

      originalWatcher.on('add', (file) => {
        const timestamp = new Date().toISOString();
        const relativePath = file.replace(process.cwd() + '/', '');
        console.error(`➕ [${timestamp}] File added: ${relativePath}`);
      });

      originalWatcher.on('unlink', (file) => {
        const timestamp = new Date().toISOString();
        const relativePath = file.replace(process.cwd() + '/', '');
        console.error(`❌ [${timestamp}] File deleted: ${relativePath}`);
      });
    } else {
      console.error('❌ [Rebuild Plugin] NO WATCHER FOUND!');
    }
  },
}

// Error Interception Plugin - Catches and logs full stack traces from esbuild
// This helps us see the actual error, not just "source.split is not a function"
const errorInterceptionPlugin = {
  name: 'error-interception',
  apply: 'serve',
  // Note: No enforce specified - let Vue plugin run first to handle .vue files

  async resolveId(id, importer) {
    // Trace all imports that happen during dynamic-workspace loading
    if (id.includes('dynamic-workspace') || id.includes('i18n') || importer?.includes('dynamic-workspace')) {
      console.error(`\n📌 [RESOLVE TRACE] Import detected`);
      console.error(`   ID: ${id}`);
      console.error(`   Importer: ${importer || 'entry point'}`);
    }
  },

  async load(id) {
    // Trace all file loads
    if (id.includes('dynamic-workspace') || id.includes('i18n') || id.includes('main.ts')) {
      console.error(`\n📂 [LOAD TRACE] File loading`);
      console.error(`   ID: ${id}`);
    }
  },

  async transform(code, id) {
    // Log what we're transforming (only if code is a string)
    if (typeof code === 'string' && (id.includes('main.ts') || id.includes('dynamic-workspace') || id.includes('i18n'))) {
      console.error(`\n🔄 [TRANSFORM START] ${id.substring(id.lastIndexOf('/'))}`);
      console.error(`   Code length: ${code.length} bytes`);
      console.error(`   First 100 chars: ${code.substring(0, 100)}`);
    }
    return null; // Let other plugins handle it
  },

  configureServer(server) {
    // Hook into Vite's error handler to catch middleware errors
    const originalUse = server.middlewares.use;
    server.middlewares.use = function(...args) {
      const fn = args[args.length - 1];
      if (typeof fn === 'function') {
        const wrappedFn = (req, res, next) => {
          try {
            const result = fn(req, res, (err) => {
              if (err) {
                console.error('\n❌ [MIDDLEWARE ERROR CAUGHT]');
                console.error(`   Path: ${req.url}`);
                console.error(`   Error: ${err.message}`);
                console.error(`   Error details:`, err);
                if (err.frame) {
                  console.error(`   Frame:\n${err.frame}`);
                }
                if (err.id) {
                  console.error(`   File ID: ${err.id}`);
                }
                if (err.plugin) {
                  console.error(`   Plugin: ${err.plugin}`);
                }
                console.error(`   Stack: ${err.stack}`);
              }
              next(err);
            });
            if (result instanceof Promise) {
              result.catch((err) => {
                console.error('\n❌ [ASYNC MIDDLEWARE ERROR]');
                console.error(`   Path: ${req.url}`);
                console.error(`   Error: ${err.message}`);
                console.error(`   Error details:`, err);
                if (err.frame) {
                  console.error(`   Frame:\n${err.frame}`);
                }
                if (err.id) {
                  console.error(`   File ID: ${err.id}`);
                }
                if (err.plugin) {
                  console.error(`   Plugin: ${err.plugin}`);
                }
                console.error(`   Stack: ${err.stack}`);
              });
            }
            return result;
          } catch (err) {
            console.error('\n❌ [SYNC MIDDLEWARE ERROR]');
            console.error(`   Path: ${req.url}`);
            console.error(`   Error: ${err.message}`);
            console.error(`   Error details:`, err);
            console.error(`   Stack: ${err.stack}`);
            throw err;
          }
        };
        args[args.length - 1] = wrappedFn;
      }
      return originalUse.apply(this, args);
    };
  },
}

// Viewer Warmup Plugin - Pre-compile viewers on startup
// Automatically discovers and pre-compiles all viewers to avoid cold-start delays
const viewerWarmupPlugin = {
  name: 'viewer-warmup',
  apply: 'serve',
  enforce: 'post',

  async configureServer(server) {
    // Schedule warmup after server is ready
    setTimeout(async () => {
      try {
        const viewersDir = path.resolve(process.cwd(), 'canonical/viewers')

        // Check if viewers directory exists
        if (!fs.existsSync(viewersDir)) {
          console.error('❌ [Viewer Warmup] Viewers directory not found:', viewersDir)
          return
        }

        const viewers = fs.readdirSync(viewersDir).filter(f => {
          return fs.statSync(path.join(viewersDir, f)).isDirectory()
        })

        console.error('\n' + '━'.repeat(100))
        console.error('🔥 VIEWER WARMUP STARTED')
        console.error(`   Found ${viewers.length} viewers to pre-compile`)
        console.error('━'.repeat(100) + '\n')

        let successCount = 0
        let failCount = 0

        for (const viewer of viewers) {
          const viewerUrl = `http://localhost:5052/canonical/viewers/${viewer}/main.ts`
          try {
            const startTime = performance.now()
            const response = await fetch(viewerUrl)
            const duration = (performance.now() - startTime).toFixed(2)

            if (response.ok) {
              console.error(`  ✅ ${viewer.padEnd(30)} ${duration.padStart(6)}ms`)
              successCount++
            } else {
              console.error(`  ⚠️  ${viewer.padEnd(30)} HTTP ${response.status}`)
              failCount++
            }
          } catch (error) {
            console.error(`  ❌ ${viewer.padEnd(30)} ${error.message}`)
            failCount++
          }
        }

        console.error('\n' + '─'.repeat(100))
        console.error(`✅ VIEWER WARMUP COMPLETED: ${successCount}/${viewers.length} pre-compiled`)
        console.error('─'.repeat(100) + '\n')
      } catch (error) {
        console.error('❌ [Viewer Warmup] Error:', error.message)
      }
    }, 2000) // Wait 2s for Vite to initialize
  },
}

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

// Plugin to handle URL rewriting for /artifacts/* and /viewers/* requests
// - /artifacts/* URLs → /* for file serving
// - /viewers/:viewerName → /canonical/viewers/:viewerName/ (SPA serving)
const urlRewritePlugin = {
  name: 'url-rewrite',
  apply: 'serve',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      // Rewrite /artifacts/* URLs to /* for file serving
      if (req.url.startsWith('/artifacts/')) {
        req.url = req.url.replace('/artifacts', '')
        return next()
      }

      // Rewrite /viewers/:viewerName to /canonical/viewers/:viewerName/
      // This allows Vite to serve the index.html from canonical structure
      const match = req.url?.match(/^\/viewers\/([^/?#]+)(\/)?(\?.*)?$/)
      if (match) {
        const viewerName = match[1]
        req.url = `/canonical/viewers/${viewerName}/`
      }

      next()
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
    performanceTracingPlugin,
    rebuildObservabilityPlugin,
    errorInterceptionPlugin,
    viewerWarmupPlugin,
    migrationWarningPlugin,
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
    watch: {
      // TRUE WHITELIST: Only watch .ts, .vue, .js files
      // Ignore EVERYTHING else (auto-generated files, data, assets, etc)
      // This prevents recompilation when SCHEMAS.json or other non-source files change
      ignored: [
        '**/*',              // Ignore everything by default
        '!**/*.ts',          // EXCEPT: TypeScript files
        '!**/*.vue',         // EXCEPT: Vue components
        '!**/*.js',          // EXCEPT: JavaScript files
      ],

      // Chokidar polling for Docker volumes on Windows
      // REQUIRED: Native inotify doesn't work with Docker volumes on Windows
      // Values: aggregateTimeout groups rapid changes, poll is check interval
      // These values prevent continuous recompilation while detecting changes
      usePolling: process.env.VITE_CHOKIDAR_USEPOLLING !== 'false',
      aggregateTimeout: 1000,  // Wait 1s before triggering update
      poll: 3000,              // Check for changes every 3s (slower = less CPU)
    },

    // CORS configuration for cross-origin requests from frontend
    // Can be overridden with VITE_CORS_ORIGINS environment variable
    cors: {
      origin: (() => {
        const origins = process.env.VITE_CORS_ORIGINS || 'http://localhost:8000,http://localhost:5173,http://localhost:5050'
        return typeof origins === 'string' ? origins.split(',') : ['http://localhost:8000', 'http://localhost:5173', 'http://localhost:5050']
      })(),
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
    sourcemap: true,  // Keep source maps for debugging
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
  logLevel: 'debug',  // Enable verbose logging to trace esbuild issues
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
