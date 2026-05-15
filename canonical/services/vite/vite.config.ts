/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

// ESM doesn't have __dirname, so we create it
const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Utility: Format timestamp for logs
const getTimestamp = () => new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })

// Performance Tracing Plugin - Detailed startup timing with timestamps
// FIXED: Now uses Map to track timings outside of hook return values
// This prevents interference with esbuild's source code processing
const performanceTracingPlugin = (() => {
  const timingMap = new Map(); // Track: id → startTime
  const resolveThresholdMs = 50;
  const loadThresholdMs = 100;

  return {
    name: 'performance-tracing',
    apply: 'serve',
    enforce: 'post', // Run after other plugins to avoid interfering with resolution

    resolveId(id) {
      const shouldTrace = process.env.VITE_TRACE === 'true' || process.env.VITE_TRACE_RESOLVE === 'true';
      if (shouldTrace) {
        timingMap.set(`resolve:${id}`, performance.now());
      }
      // CRITICAL: Return nothing to let other plugins handle resolution
      return null;
    },

    load(id) {
      const shouldTrace = process.env.VITE_TRACE === 'true' || process.env.VITE_TRACE_LOAD === 'true';
      if (shouldTrace) {
        timingMap.set(`load:${id}`, performance.now());
      }
      // CRITICAL: Return nothing to let Vite's default load handler process the file
      return null;
    },

    transform(code, id) {
      const shouldTrace = process.env.VITE_TRACE === 'true';

      if (shouldTrace) {
        // Log resolution timing if we tracked it
        const resolveKey = `resolve:${id}`;
        if (timingMap.has(resolveKey)) {
          const duration = (performance.now() - timingMap.get(resolveKey)).toFixed(2);
          if (parseInt(duration) > resolveThresholdMs) {
            console.error(`[${getTimestamp()}] ⏱️ [RESOLVE] ${duration.padStart(6)}ms | ${id}`);
          }
          timingMap.delete(resolveKey);
        }

        // Log load timing if we tracked it
        const loadKey = `load:${id}`;
        if (timingMap.has(loadKey)) {
          const duration = (performance.now() - timingMap.get(loadKey)).toFixed(2);
          if (parseInt(duration) > loadThresholdMs) {
            console.error(`[${getTimestamp()}] ⏱️ [LOAD] ${duration.padStart(6)}ms | ${id}`);
          }
          timingMap.delete(loadKey);
        }
      }

      // Return nothing - let other plugins handle transformation
      return null;
    },

    configureServer(server) {
      const initStart = performance.now();
      const shouldTrace = process.env.VITE_TRACE === 'true';
      const timestamp = getTimestamp();

      console.error('\n' + '━'.repeat(100));
      console.error(`[${timestamp}] 🚀 VITE INITIALIZATION STARTED`);
      console.error(`   Trace enabled: ${shouldTrace}`);
      console.error(`   Node env: ${process.env.NODE_ENV}`);
      console.error(`   Root: ${__dirname}`);
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
  };
})()

// Rebuild Observability Plugin - Logs file change triggers
const rebuildObservabilityPlugin = {
  name: 'rebuild-observability',
  apply: 'serve',
  handleHotUpdate({ file, server, modules }) {
    const timestamp = new Date().toISOString();
    const relativePath = file.replace(__dirname + '/', '');
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
        const relativePath = file.replace(__dirname + '/', '');
        console.error(`📝 [${timestamp}] File changed: ${relativePath}`);
      });

      originalWatcher.on('add', (file) => {
        const timestamp = new Date().toISOString();
        const relativePath = file.replace(__dirname + '/', '');
        console.error(`➕ [${timestamp}] File added: ${relativePath}`);
      });

      originalWatcher.on('unlink', (file) => {
        const timestamp = new Date().toISOString();
        const relativePath = file.replace(__dirname + '/', '');
        console.error(`❌ [${timestamp}] File deleted: ${relativePath}`);
      });
    } else {
      console.error('❌ [Rebuild Plugin] NO WATCHER FOUND!');
    }
  },
}

// File Processing Tracker - Global tracking of what Vite is processing
let currentFile = null
let processingStack = []

const fileProcessingTracker = {
  name: 'file-processing-tracker',
  apply: 'serve',

  async resolveId(id, importer) {
    // Track resolution chain
    if (id.includes('dynamic-workspace') || id.includes('i18n') || id.includes('App') || id.endsWith('.vue')) {
      console.error(`\n[RESOLVE] ${id}`);
      console.error(`  ← from: ${importer || '(entry)'}`);
    }
  },

  async load(id) {
    // Track file loads
    processingStack.push(id)
    currentFile = id
    if (id.includes('dynamic-workspace') || id.includes('i18n') || id.includes('App') || id.includes('shared')) {
      console.error(`\n[LOAD] ${id}`);
    }
  },

  async transform(code, id) {
    // Track transformations - THIS IS WHERE ERRORS HAPPEN
    processingStack.push(id)
    currentFile = id

    if (typeof code === 'string') {
      if (id.includes('main.ts') || id.includes('App.vue') || id.includes('i18n') || id.includes('composables')) {
        console.error(`\n🔄 [TRANSFORM] ${id}`);
        console.error(`   Stack: ${processingStack.slice(-3).join(' → ')}`);
      }
    }
    return null
  },
}

// Error Interception Plugin - Catches and logs full stack traces from esbuild
const errorInterceptionPlugin = {
  name: 'error-interception',
  apply: 'serve',

  configureServer(server) {
    const originalUse = server.middlewares.use;
    server.middlewares.use = function(...args) {
      const fn = args[args.length - 1];
      if (typeof fn === 'function') {
        const wrappedFn = (req, res, next) => {
          try {
            const result = fn(req, res, (err) => {
              if (err) {
                console.error('\n' + '█'.repeat(100));
                console.error('🚨 ERROR DURING FILE PROCESSING');
                console.error('█'.repeat(100));
                console.error(`\n📍 Current file: ${currentFile}`);
                console.error(`📚 Processing stack:`);
                processingStack.slice(-5).forEach((f, idx) => {
                  console.error(`   ${idx + 1}. ${f}`);
                });
                console.error(`\n❌ Error: ${err.message}`);
                console.error(`📍 Location: ${req.url}`);
                console.error(`🔌 Plugin: ${err.plugin || 'unknown'}`);
                console.error(`📄 File ID: ${err.id || 'unknown'}`);
                console.error('\n' + '█'.repeat(100));
              }
              next(err);
            });
            if (result instanceof Promise) {
              result.catch((err) => {
                console.error('\n🚨 [ASYNC ERROR]');
                console.error(`   Current: ${currentFile}`);
                console.error(`   Error: ${err.message}`);
              });
            }
            return result;
          } catch (err) {
            console.error('\n🚨 [SYNC ERROR]');
            console.error(`   Current: ${currentFile}`);
            console.error(`   Error: ${err.message}`);
            throw err;
          }
        };
        args[args.length - 1] = wrappedFn;
      }
      return originalUse.apply(this, args);
    };
  },
}

// Viewer Warmup Plugin - Pre-compile viewer sources on startup
// Automatically discovers viewers and pre-compiles main.ts to avoid cold-start delays
const viewerWarmupPlugin = {
  name: 'viewer-warmup',
  apply: 'serve',
  enforce: 'post',

  async configureServer(server) {
    // Schedule warmup after server is ready
    setTimeout(async () => {
      try {
        const viewersDir = path.resolve(__dirname, 'canonical/viewers')

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
        console.error(`   Found ${viewers.length} viewers to pre-compile main.ts`)
        console.error('━'.repeat(100) + '\n')

        let successCount = 0
        let failCount = 0

        for (const viewer of viewers) {
          // Pre-compile main.ts (TypeScript compilation)
          // This triggers: TS → Vue template processing → CSS compilation (JIT)
          const mainTsUrl = `http://localhost:5052/canonical/viewers/${viewer}/main.ts`

          try {
            const start = performance.now()
            const response = await fetch(mainTsUrl)
            const duration = (performance.now() - start).toFixed(2)

            if (response.ok) {
              console.error(`  ✅ ${viewer.padEnd(30)} main.ts compiled in ${duration.padStart(5)}ms`)
              successCount++
            } else {
              console.error(`  ⚠️  ${viewer.padEnd(30)} main.ts returned HTTP ${response.status}`)
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

// Cell Type Warmup Plugin - Pre-compile cell type View.vue on startup
// Prevents cold-start delay when cells are added to notebook for the first time
// Scan is automatic: discovers cell types from canonical/cell_types/ directory
const cellTypeWarmupPlugin = {
  name: 'cell-type-warmup',
  apply: 'serve',
  enforce: 'post',

  async configureServer(server) {
    // Schedule warmup after viewer warmup completes (3.5s vs viewer's 2s)
    setTimeout(async () => {
      try {
        const cellTypesDir = path.resolve(__dirname, 'canonical/cell_types')

        // Check if cell types directory exists
        if (!fs.existsSync(cellTypesDir)) {
          console.error('❌ [Cell Type Warmup] Directory not found:', cellTypesDir)
          return
        }

        const cellTypes = fs.readdirSync(cellTypesDir).filter(f => {
          return fs.statSync(path.join(cellTypesDir, f)).isDirectory()
        })

        console.error('\n' + '━'.repeat(100))
        console.error('🔥 CELL TYPE WARMUP STARTED')
        console.error(`   Found ${cellTypes.length} cell types`)
        console.error('━'.repeat(100) + '\n')

        let successCount = 0
        let skippedCount = 0
        let failCount = 0

        for (const cell of cellTypes) {
          const viewPath = path.join(cellTypesDir, cell, 'frontend', 'View.vue')

          // Skip cells without frontend/View.vue (headless or type.json only)
          if (!fs.existsSync(viewPath)) {
            console.error(`  ⏭️  ${cell.padEnd(30)} No frontend/View.vue, skipping`)
            skippedCount++
            continue
          }

          // Pre-compile View.vue (Vue SFC compilation)
          // This triggers: Vue template → TypeScript → CSS compilation (JIT)
          // Imports inside View.vue (composables, stores, BaseCell types) are
          // resolved transitively by Vite's normal pipeline
          const viewUrl = `http://localhost:5052/canonical/cell_types/${cell}/frontend/View.vue`

          try {
            const start = performance.now()
            const response = await fetch(viewUrl)
            const duration = (performance.now() - start).toFixed(2)

            if (response.ok) {
              console.error(`  ✅ ${cell.padEnd(30)} View.vue compiled in ${duration.padStart(5)}ms`)
              successCount++
            } else {
              console.error(`  ⚠️  ${cell.padEnd(30)} View.vue returned HTTP ${response.status}`)
              failCount++
            }
          } catch (error) {
            console.error(`  ❌ ${cell.padEnd(30)} ${error.message}`)
            failCount++
          }
        }

        console.error('\n' + '─'.repeat(100))
        console.error(`✅ CELL TYPE WARMUP COMPLETED: ${successCount} compiled, ${skippedCount} skipped, ${failCount} failed`)
        console.error('─'.repeat(100) + '\n')
      } catch (error) {
        console.error('❌ [Cell Type Warmup] Error:', error.message)
      }
    }, 3500) // Wait 3.5s (after viewer warmup at 2s) for server readiness
  },
}

// Request Logger Plugin - Logs all HTTP requests processed by Vite
const requestLoggerPlugin = {
  name: 'request-logger',
  apply: 'serve',

  configureServer(server) {
    const shouldLog = process.env.VITE_REQUEST_LOG === 'true';

    if (!shouldLog) return;

    // Track request start times
    const requestMap = new Map();

    server.middlewares.use((req, res, next) => {
      const timestamp = getTimestamp();
      const requestId = `${req.method}-${req.url}-${Date.now()}`;
      const startTime = performance.now();

      requestMap.set(requestId, { startTime, timestamp, method: req.method, url: req.url });

      // Log incoming request
      console.error(`[${timestamp}] 📥 ${req.method.padEnd(6)} ${req.url}`);

      // Intercept response to log completion
      const originalEnd = res.end;
      res.end = function(...args) {
        const duration = (performance.now() - startTime).toFixed(2);
        const statusCode = res.statusCode;
        const statusColor = statusCode >= 400 ? '❌' : statusCode >= 300 ? '⚠️ ' : '✅';
        const completionTime = getTimestamp();

        console.error(`[${completionTime}] ${statusColor} ${req.method.padEnd(6)} ${req.url.padEnd(50)} | HTTP ${statusCode} (${duration}ms)`);

        requestMap.delete(requestId);
        return originalEnd.apply(res, args);
      };

      next();
    });
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

// Plugin to handle URL rewriting for /artifacts/* and /viewers/* requests
// - /artifacts/* URLs → /* for file serving
// - /viewers/:viewerName → serve index.html
const urlRewritePlugin = {
  name: 'url-rewrite',
  apply: 'serve',
  configureServer(server) {
    console.error(`[url-rewrite] MIDDLEWARE INITIALIZED`)
    console.error(`[url-rewrite] __dirname: "${__dirname}"`)

      // Debug middleware: Capture headers for artifact paths
      server.middlewares.use((req, res, next) => {
        if (req.url.includes('/canonical') || req.url.includes('/sandbox') || req.url.includes('/runtime')) {
          console.error(`[DEBUG-HEADERS] Request URL: ${req.url}`)
          console.error(`[DEBUG-HEADERS] Host: ${req.headers.host}`)
          console.error(`[DEBUG-HEADERS] X-Forwarded-Host: ${req.headers['x-forwarded-host'] || 'NOT SET'}`)
          console.error(`[DEBUG-HEADERS] X-Forwarded-Proto: ${req.headers['x-forwarded-proto'] || 'NOT SET'}`)
          console.error(`[DEBUG-HEADERS] Origin: ${req.headers.origin || 'NOT SET'}`)
          console.error(`[DEBUG-HEADERS] Referer: ${req.headers.referer || 'NOT SET'}`)
          console.error(`[DEBUG-HEADERS] All headers:`, req.headers)
        }

        // Intercept response to catch 403 (using res.end which is always called)
        const originalEnd = res.end
        res.end = function(chunk, encoding, callback) {
          if (req.url.includes('/canonical') || req.url.includes('/sandbox') || req.url.includes('/runtime')) {
            console.error(`[DEBUG-403] Status: ${res.statusCode} for ${req.url}`)
            if (res.statusCode === 403) {
              console.error(`[DEBUG-403] 403 DETECTED!`)
              console.error(`[DEBUG-403] Chunk type: ${typeof chunk}`)
              if (chunk) {
                console.error(`[DEBUG-403] Response body (first 500 chars):`, chunk.toString().slice(0, 500))
              }
            }
          }
          return originalEnd.call(this, chunk, encoding, callback)
        }

        next()
      })

      server.middlewares.use((req, res, next) => {
        const url = req.url || '/'

        // CRITICAL: Allow WebSocket upgrades to pass through without rewrite
        // HMR client needs raw WebSocket, not HTML redirects
        if (req.headers.upgrade === 'websocket' || req.headers.connection?.includes('Upgrade')) {
          console.error(`[url-rewrite] WebSocket upgrade detected, passing through: ${url}`)
          return next()
        }

        // Match /artifacts/canonical/viewers/:viewerName ONLY (root of viewer, not subpaths)
        // Pattern: /artifacts/canonical/viewers/{viewerName}[?query]
        // Examples: /artifacts/canonical/viewers/dynamic-workspace, /artifacts/canonical/viewers/dynamic-workspace?v=123
        // NOT: /artifacts/canonical/viewers/dynamic-workspace/main.ts (let Vite serve files)
        const regex = /^\/artifacts\/canonical\/viewers\/([^/?#]+)(\?.*)?$/
        console.error(`[url-rewrite] PATTERN: ${regex.source}`)
        console.error(`[url-rewrite] TESTING: ${url} against pattern`)

        const match = url.match(regex)
        if (match) {
          const viewerName = match[1]
          const indexPath = `/canonical/viewers/${viewerName}/index.html`
          const fullPath = path.join(__dirname, indexPath)

          console.error(`[url-rewrite] ✅ MATCHED viewer: ${viewerName}`)
          console.error(`[url-rewrite] Reading from: ${fullPath}`)

          try {
            // Check if file exists first
            if (!fs.existsSync(fullPath)) {
              console.error(`[url-rewrite] ❌ FILE NOT FOUND: ${fullPath}`)
              return next()
            }

            // Read and serve index.html
            const html = fs.readFileSync(fullPath, 'utf-8')
            console.error(`[url-rewrite] ✅ FILE READ: ${fullPath.length} bytes`)
            console.error(`[url-rewrite] ✅ SERVING index.html for ${viewerName}`)
            res.setHeader('Content-Type', 'text/html; charset=utf-8')
            res.end(html)
            return
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            console.error(`[url-rewrite] ❌ ERROR: ${msg}`)
            return next()
          }
        }

        // Fallback: Handle root path (/)
        if (url === '/' || url === '') {
          console.error(`[url-rewrite] ROOT REQUEST: Serving fallback`)

          // Try to serve index.html from artifacts root
          const indexPath = path.join(__dirname, 'index.html')

          if (fs.existsSync(indexPath)) {
            console.error(`[url-rewrite] ROOT: Found index.html at ${indexPath}`)
            try {
              const html = fs.readFileSync(indexPath, 'utf-8')
              res.setHeader('Content-Type', 'text/html; charset=utf-8')
              res.end(html)
              return
            } catch (err) {
              const msg = err instanceof Error ? err.message : String(err)
              console.error(`[url-rewrite] ROOT: Error reading index.html: ${msg}`)
            }
          } else {
            console.error(`[url-rewrite] ROOT: No index.html found, redirecting to viewer`)
            // Fallback: redirect to first available viewer
            res.writeHead(302, { Location: '/viewers/dynamic-workspace' })
            res.end()
            return
          }
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

console.error('\n🔥 [VITE CONFIG LOADED] Version 2026-04-19T18:30 - ALL MIDDLEWARES RE-ENABLED (HMR WORKING)\n')

export default defineConfig({
  root: '/app/artifacts',  // Actual directory where canonical/, shared/ files are located
  base: '/artifacts/',  // Requests come as /artifacts/canonical/...; remove /artifacts/ to resolve files
  cacheDir: '/app/artifacts/.vite',  // Absolute path to cache (node_modules fica em /app/artifacts/node_modules)
  plugins: [
    // HMR Debug plugin - auto-enable HMR logging in browser
    {
      name: 'auto-hmr-debug',
      apply: 'serve',
      transformIndexHtml(html) {
        return html.replace(
          '<head>',
          `<head>
      <script>
        // Auto-enable HMR debug logging for troubleshooting
        localStorage.setItem('debug', 'vite:hmr');
        console.log('%c[VITE-HMR] Debug mode activated automatically', 'color: #00cc66; font-weight: bold; font-size: 12px;');
      </script>`
        )
      }
    },

    // Performance tracing (development profiling)
    performanceTracingPlugin,

    // Request logging (detailed HTTP activity)
    requestLoggerPlugin,

    // Rebuild observability (file change tracking)
    rebuildObservabilityPlugin,

    // File processing tracker (module resolution chain)
    fileProcessingTracker,

    // Error interception (full stack traces)
    errorInterceptionPlugin,

    // Viewer pre-compilation warmup
    viewerWarmupPlugin,

    // Cell type pre-compilation warmup (avoids cold-start on first cell load)
    cellTypeWarmupPlugin,

    // URL rewrite middleware (handles /artifacts/canonical/viewers/* and root /)
    urlRewritePlugin,

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

    // Host validation: Allow internal Docker service name + external hosts
    // Vite validates Host header against this list
    allowedHosts: [
      'all',           // Supposedly disables validation, but test shows it doesn't work
      'vite',          // Docker service name (internal)
      'vite:5052',     // With port
      'localhost',
      '127.0.0.1',
      'scare.scareverse.net',
      'hub-staging.scareverse.net',
      'hub.scareverse.net',
    ],

    // HMR (Hot Module Replacement) configuration
    // Browser connects to external host:port, Vite listens internally on 5052
    hmr: process.env.VITE_HMR_HOST ? {
      host: process.env.VITE_HMR_HOST,
      protocol: process.env.VITE_HMR_PROTOCOL || 'wss',
      path: '/__vite_hmr',
    } : true,

    // Serve files from artifacts root
    fs: {
      // Auth-Proxy is the ingress controller:
      // - Validates session (who is authenticated)
      // - Validates RBAC (who can access /runtime, /sandbox, /canonical)
      // - Only authenticated + authorized requests reach Vite
      //
      // So Vite can trust that any request it gets has already been validated.
      // TEMPORARY TEST: Allow all paths to identify if fs.allow is the culprit
      allow: ['/'],  // Bypass all filesystem restrictions for debugging
      strict: false,  // Trust Auth-Proxy to do its job
    },
  },
  
  // Module resolution
  resolve: {
    alias: {
      // Use flexible paths for both container and local development
      // In container: /app/artifacts
      // In local/test: __dirname

      // Map #artifacts to artifacts root (for all cell types and composition)
      '#artifacts': __dirname,

      // Map #shared to shared infrastructure mirror (isolated utilities)
      '#shared': path.resolve(__dirname, 'shared'),

      // Map @/ to #shared for shared utilities (apiService, authService, etc)
      // This allows files that import @/utils/logger to resolve to #shared/utils/logger
      // In cockpit-vue context: @/ → cockpit-vue/src (normal)
      // In Vite context: @/ → #shared/ (this alias, preserving folder structure)
      '@': path.resolve(__dirname, 'shared'),
      '@/utils': path.resolve(__dirname, 'shared/utils'),
      '@/services': path.resolve(__dirname, 'shared/services'),
      '@/config': path.resolve(__dirname, 'shared/config'),
      '@/components': path.resolve(__dirname, 'shared/components'),
      '@/types': path.resolve(__dirname, 'shared/types'),
      '@/stores': path.resolve(__dirname, 'shared/stores'),
      '@/composables': path.resolve(__dirname, 'shared/composables'),
      '@/i18n': path.resolve(__dirname, 'shared/i18n'),

      // Force npm packages to resolve from node_modules inside __dirname
      // (root is /app but node_modules is at /app/artifacts/node_modules)
      'vue': path.resolve(__dirname, 'node_modules/vue'),
      '@vue/runtime-core': path.resolve(__dirname, 'node_modules/@vue/runtime-core'),
      '@vue/runtime-dom': path.resolve(__dirname, 'node_modules/@vue/runtime-dom'),
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
  clearScreen: false,  // Don't clear terminal on startup (change detection test 2026-04-05)
  
  // Test configuration
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    root: __dirname,  // Use current working directory for tests
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
